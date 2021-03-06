from fenics import *
from dolfin import *
import numpy as np
import csv
import sys
import os
import argparse
import json
import ast
from pprint import pprint
from materials_properties import *
import inspect

def byteify(input):
    if isinstance(input, dict):
        return {byteify(key): byteify(value)
                for key, value in input.iteritems()}
    elif isinstance(input, list):
        return [byteify(element) for element in input]
    elif isinstance(input, unicode):
        return input.encode('utf-8')
    else:
        return input

def update_bc(t,physic):
  bcs=list()
  for DC in data['physics'][physic]['boundary_conditions']['dc']:
    #value_DC=DC['value'] #todo make this value able to be an Expression (time or space dependent)
    value_DC=Expression(DC['value'],t=t,degree=2)
    if type(DC['surface'])==list:
      for surface in DC['surface']:
        #print(surface)
        bci=DirichletBC(V,value_DC,surface_marker,surface)
        bcs.append(bci)
        #print(bci_T)
    else:
      print(DC)
      bci=DirichletBC(V,value_DC,surface_marker,DC['surface'])
      bcs.append(bci)
      #print(bci_T)
  return bcs

print('Getting the databases')




#xdmf_encoding = XDMFFile.Encoding.ASCII

#xdmf_encoding = XDMFFile.Encoding.HDF5


MOT_parameters='MOT_parameters_RCB.json'
with open(MOT_parameters) as f:
    data = json.load(f)
data=byteify(data)

print('Getting the solvers')
if data['physics']['solve_heat_transfer']==1:
  solve_heat_transfer=True
else:
  solve_heat_transfer=False
if data['physics']['solve_tritium_diffusion']==1:
  solve_diffusion=True
else:
  solve_diffusion=False
if data['physics']['diffusion_coeff_temperature_dependent']==1:
  solve_diffusion_coefficient_temperature_dependent=True
else:
  solve_diffusion_coefficient_temperature_dependent=False
if data['physics']['solve_with_decay']==1:
  solve_with_decay=True
else:
  solve_with_decay=False

calculate_off_gassing=True



print('Defining the solving parameters')
Time = float(data["solving_parameters"]['final_time'])  #60000*365.25*24*3600.0# final time 
num_steps = data['solving_parameters']['number_of_time_steps'] # number of time steps
dt = Time / num_steps # time step size
t=0 #Initialising time to 0s



print('Defining mesh')
# Read in Mesh and markers from file
mesh = Mesh()
xdmf_in = XDMFFile(mesh.mpi_comm(), str(data['mesh_file']))
xdmf_in.read(mesh)
# prepare output file for writing by writing the mesh to the file
#xdmf_out = XDMFFile(str(data['mesh_file']).split('.')[1]+'_from_fenics.xdmf')

subdomains = MeshFunction("size_t", mesh, mesh.topology().dim())
print('Number of cell is '+ str(len(subdomains.array())))


print('Defining Functionspaces')
V = FunctionSpace(mesh, 'P', 1) #FunctionSpace of the solution c
V0 = FunctionSpace(mesh, 'DG', 0) #FunctionSpace of the materials properties

### Define initial values
print('Defining initial values')
##Tritium concentration
if solve_diffusion==True:
  #print(str(data['physics']['tritium_diffusion']['initial_value']))
  iniC = Expression(str(data['physics']['tritium_diffusion']['initial_value']),degree=2) 
  c_n = interpolate(iniC, V)
##Temperature
if solve_heat_transfer==True:
  #print(str(data['physics']['heat_transfers']['initial_value']))
  iniT = Expression(str(data['physics']['heat_transfers']['initial_value']),degree=2) 
  T_n = interpolate(iniT, V)


### Boundary Conditions
print('Defining boundary conditions')

# read in Surface markers for boundary conditions
surface_marker_mvc = MeshValueCollection("size_t", mesh, mesh.topology().dim() - 1)
xdmf_in.read(surface_marker_mvc, "surface_marker")

surface_marker_mvc.rename("surface_marker", "surface_marker")
#xdmf_out.write(surface_marker_mvc, xdmf_encoding)

surface_marker = MeshFunction("size_t", mesh, surface_marker_mvc)

ds = Measure('ds', domain=mesh, subdomain_data = surface_marker)

##Tritium Diffusion
if solve_diffusion==True:
  #DC
  bcs_c=list()
  for DC in data['physics']['tritium_diffusion']['boundary_conditions']['dc']:
    value_DC=Expression(DC['value'],t=0,degree=2)
    if type(DC['surface'])==list:
      for surface in DC['surface']:
        #print(surface)
        bci_c=DirichletBC(V,value_DC,surface_marker,surface)
        bcs_c.append(bci_c)
        #print(bci_T)
    else:
      #print(DC)
      bci_c=DirichletBC(V,value_DC,surface_marker,DC['surface'])
      bcs_c.append(bci_c)
      #print(bci_T)


  #Neumann
  Neumann_BC_c_diffusion=[]
  for Neumann in data['physics']['tritium_diffusion']['boundary_conditions']['neumann']:
    value=Neumann['value']
    
    if type(Neumann['surface'])==list:
      for surface in Neumann['surface']:
        Neumann_BC_c_diffusion.append([ds(surface),value])
    else:
      Neumann_BC_c_diffusion.append([ds(Neumann['surface']),value])


  #Robins
  Robin_BC_c_diffusion=[]
  for Robin in data['physics']['tritium_diffusion']['boundary_conditions']['robin']:
    value=Function(V)
    k=3.56e-8
    value=eval(Robin['value'])
    #value=conditional(gt(c_n, 0), k*(c_n)**0.74, Constant(0.0))
    if type(Robin['surface'])==list:
      for surface in Robin['surface']:
        Robin_BC_c_diffusion.append([ds(surface),value])
    else:
      Robin_BC_c_diffusion.append([ds(Robin['surface']),value])



##Temperature
if solve_heat_transfer==True:
  #DC
  bcs_T=list()
  for DC in data['physics']['heat_transfers']['boundary_conditions']['dc']:
    #value_DC=DC['value'] #todo make this value able to be an Expression (time or space dependent)
    value_DC=Expression(DC['value'],t=0,degree=2)
    if type(DC['surface'])==list:
      for surface in DC['surface']:
        #print(surface)
        bci_T=DirichletBC(V,value_DC,surface_marker,surface)
        bcs_T.append(bci_T)
        #print(bci_T)
    else:
      #print(DC)
      bci_T=DirichletBC(V,value_DC,surface_marker,DC['surface'])
      bcs_T.append(bci_T)
      #print(bci_T)
      


  #Neumann
  Neumann_BC_T_diffusion=[]
  for Neumann in data['physics']['heat_transfers']['boundary_conditions']['neumann']:
    value=Neumann['value']
    
    if type(Neumann['surface'])==list:
      for surface in Neumann['surface']:
        Neumann_BC_T_diffusion.append([ds(surface),value])
    else:
      Neumann_BC_T_diffusion.append([ds(Neumann['surface']),value])


  #Robins
  Robin_BC_T_diffusion=[]
  for Robin in data['physics']['heat_transfers']['boundary_conditions']['robin']:
    
    if type(Robin['surface'])==list:
      for surface in Robin['surface']:
        Robin_BC_T_diffusion.append([ds(surface),Robin['hc_coeff'],Robin['t_amb']])
    else:
      Robin_BC_T_diffusion.append([ds(Robin['surface']),Robin['hc_coeff'],Robin['t_amb']])
  
  #print(Neumann_BC_T_diffusion)


#read in the volume markers
volume_marker_mvc = MeshValueCollection("size_t", mesh, mesh.topology().dim())
xdmf_in.read(volume_marker_mvc, "volume_marker_material")

#volume_marker_mvc.rename("volume_marker_material", "volume_marker_material")
#xdmf_out.write(volume_marker_mvc, xdmf_encoding)

volume_marker = MeshFunction("size_t", mesh, volume_marker_mvc)
dx = Measure('dx', domain=mesh, subdomain_data=volume_marker)

###Defining materials properties
print('Defining the materials properties')

D  = Function(V0) #Diffusion coefficient
thermal_conductivity=Function(V0)
specific_heat=Function(V0)
density=Function(V0)

def calculate_D(T,material_id):
  R=8.314 #Perfect gas constant
  if material_id=="concrete": #Concrete
    return 2e-6#7.3e-7*np.exp(-6.3e3/T)
  elif material_id=="polymer": #Polymer
    return 2.0e-7*np.exp(-29000.0/R/T)
  elif material_id=="steel": #steel
    return 7.3e-7*np.exp(-6.3e3/T)#1e-16#2e-6
  else:
    print("!!ERROR!! Unable to find "+str(material_id)+" as material ID in the database "+str(inspect.stack()[0][3]))
    return sys.exit(0)
def calculate_thermal_conductivity(T,material_id):
  R=8.314 #Perfect gas constant
  if material_id=="concrete":
    return 0.5
  elif material_id=="tungsten":
    return 150
  elif material_id=="lithium_lead":
    return 50
  elif material_id=="eurofer":
    return 29
  else:
    print("!!ERROR!! Unable to find "+str(material_id)+" as material ID in the database "+str(inspect.stack()[0][3]))
    return sys.exit(0)
def calculate_specific_heat(T,material_id):
  R=8.314 #Perfect gas constant
  if material_id=="concrete":
    return 880
  elif material_id=="tungsten":
    return 130
  elif material_id=="lithium_lead":
    return 500
  elif material_id=="eurofer":
    return 675
  else:
    print("!!ERROR!! Unable to find "+str(material_id)+" as material ID in the database "+str(inspect.stack()[0][3]))
    return sys.exit(0)
def calculate_density(T,material_id):

  R=8.314 #Perfect gas constant
  if material_id=="concrete":
    return 2400
  elif material_id=="tungsten":
    return 19600
  elif material_id=="lithium_lead":
    return 11600
  elif material_id=="eurofer":
    return 7625
  else:
    print("!!ERROR!! Unable to find "+str(material_id)+" as material ID in the database "+str(inspect.stack()[0][3]))
    return sys.exit(0)

def which_material_is_it(volume_id,data):
  for material in data["structure_and_materials"]["materials"]:
    for volumes in material["volumes"]:
      if volume_id in [volumes]:
        #print('Coucou toi')
        material_id=material["material"]
        break
  return material_id


##Assigning each to each cell its properties
for cell_no in range(len(volume_marker.array())):
  volume_id=volume_marker.array()[cell_no] #This is the volume id (Trellis)
  material_id=which_material_is_it(volume_id,data)
  if solve_heat_transfer==True:
    thermal_conductivity.vector()[cell_no]=calculate_thermal_conductivity(data['physics']['heat_transfers']['initial_value'],material_id)
    density.vector()[cell_no]=calculate_density(data['physics']['heat_transfers']['initial_value'],material_id)
    specific_heat.vector()[cell_no]=calculate_specific_heat(data['physics']['heat_transfers']['initial_value'],material_id)
  if solve_diffusion==True:
    D.vector()[cell_no]=calculate_D(data['physics']['heat_transfers']['initial_value'],material_id)
  
  #print(D.vector()[cell_no])


### Define variational problem
print('Defining the variational problem')


if solve_diffusion==True:
  c = TrialFunction(V)#c is the tritium concentration
  vc = TestFunction(V)
  if solve_with_decay==True:
    decay=np.log(2)/(12.33*365.25*24*3600) #Tritium Decay constant [s-1]
  else:
    decay=0
  
  f = Expression(str(data['physics']['tritium_diffusion']['source_term']),t=0,degree=2)#This is the tritium volumetric source term 
  F=((c-c_n)/dt)*vc*dx + D*dot(grad(c), grad(vc))*dx + (-f+decay*c)*vc*dx 
  for Neumann in Neumann_BC_c_diffusion:
    F += vc * Neumann[1]*Neumann[0] 
  for Robin in Robin_BC_c_diffusion:
    F += D*vc*Robin[1]*Robin[0]
  ac,Lc= lhs(F),rhs(F)


if solve_heat_transfer==True:
  T = TrialFunction(V) #T is the temperature
  vT = TestFunction(V)
  q = Expression(str(data['physics']['heat_transfers']['source_term']),t=0,degree=2) #q is the volumetric heat source term
  
  FT = specific_heat*density*((T-T_n)/dt)*vT*dx +thermal_conductivity*dot(grad(T), grad(vT))*dx - q*vT*dx #This is the heat transfer equation     

  for Neumann in Neumann_BC_T_diffusion:
    #print(Neumann)
    FT += - vT * Neumann[1]*Neumann[0] 

  for Robin in Robin_BC_T_diffusion:
    FT += vT* Robin[1] * (T-Robin[2])*Robin[0]
  aT, LT = lhs(FT), rhs(FT) #Rearranging the equation

### Time-stepping
T = Function(V)
c = Function(V)
off_gassing=list()
output_file  = File(data["output_file"])

if calculate_off_gassing==True:
  file_off_gassing = "off_gassing.csv"

for n in range(num_steps):

  
  # Update current time
  print("t= "+str(t)+" s")
  print("t= "+str(t/3600/24/365.25)+" years")
  print(str(100*t/Time)+" %")
  t += dt
  

  # Compute solution concentration
  if solve_diffusion==True:
    f.t += dt
    solve(ac==Lc,c,bcs_c)
    output_file << (c,t)
    c_n.assign(c)
    bcs_c=update_bc(t,"tritium_diffusion")
  # Compute solution temperature
  if solve_heat_transfer==True:
    q.t += dt
    solve(aT == LT, T, bcs_T)
    output_file << (T,t)
    T_n.assign(T)
    bcs_T=update_bc(t,"heat_transfers")
  #Update the materials properties
  if solve_diffusion_coefficient_temperature_dependent==True and solve_heat_transfer==True and solve_diffusion==True:
    for cell in cells(mesh):
      cell_no=cell.index()
      material_id=volume_marker.array()[cell_no]
      Ta=0
      for i in range(0,12,3):
        Ta+=T(cell.get_vertex_coordinates()[i],cell.get_vertex_coordinates()[i+1],cell.get_vertex_coordinates()[i+2])
      Ta=Ta/4
      D_value = calculate_D(Ta,material_id)
      D.vector()[cell_no] = D_value #Assigning for each cell the corresponding diffusion coeff
  
  #Calculate off-gassing
  if calculate_off_gassing==True:
    #g=conditional(gt(c_n, 0), k*(c_n)**0.74, Constant(0.0))
    g=Robin_BC_c_diffusion[0][1]
    off_gassing_per_day=3600*24*(assemble(g*ds(1))+assemble(g*ds(2))+assemble(g*ds(3))+assemble(g*ds(4))+assemble(g*ds(5))+assemble(g*ds(6))) #off-gassing in mol/day
    i=0
    print(off_gassing_per_day)
    off_gassing.append([off_gassing_per_day,t/3600/24/365])

    with open(file_off_gassing, "w") as output:
      writer = csv.writer(output, lineterminator='\n')
      writer.writerow('ct')
      for val in off_gassing:
        writer.writerows([val])