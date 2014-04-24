#  -*- coding: iso-8859-1 -*-
# modified version of the original setenv.py from  the salome-kernel module
# removed the most crazy functions

import sys
import os
import glob
import time
import pickle
import subprocess

from salome_utils import *
from lxml import etree
from lxml.builder import E
from collections import Iterable

# salome_subdir variable is used for composing paths like
# $KERNEL_ROOT_DIR/share/salome/resources, etc.  before moving to SUIT-based
# gui, instead of salome_subdir there was args['appname'] used.  but after -
# 'appname'  = "SalomeApp", so using it in making the subdirectory is an error.
salome_subdir = "salome"


def collect_module_data(modules_path):
    data = {}
    python_version="python%d.%d" % sys.version_info[0:2]
    for x in os.listdir(modules_path):
        if os.path.isdir(os.path.join(modules_path,x)):
            name = x.split('_')[0]
            root = os.path.join(modules_path,x)
            site = os.path.join(
                root,'lib',python_version,'site-packages','salome')
            resources = os.path.join(
                root,'share','salome','resources',name.lower())
            bindir = os.path.join(root,'bin','salome')
            data[name] = {
                'root':root,
                'bin':bindir,
                'lib':os.path.join(root,'lib','salome'),
                'site-packages':site,
                'shared_modules':os.path.join(site,'shared_modules'),
                'resources':resources,
                #if not name.lower().endswith('plugin'):
                'catalog':os.path.join(resources,'%sCatalog.xml'%name),
            }

    return data

def create_config_template(modules_path):
    modules = collect_module_data(modules_path)
    return {
        'env':{
            # SMESH expects a environment variable describing the meshers, lets create
            # it
            'SMESH_MeshersList':get_meshers(modules),
        },
        'modules':modules,
    }

def get_meshers(modules_config):
    meshers = []
    for key,val in modules_config.items():
        for xmlpath in glob.glob(
            os.path.join(val['resources'],'*.xml')):
            try:
                doc = etree.parse(xmlpath)
                gr = doc.find('meshers-group')
                if gr != None:
                    meshers.append(gr.get('resources'))
            except etree.XMLSyntaxError as e:
                pass
    return meshers

def add_path(directory, variable_name):
    """Function helper to add environment variables"""
    if not variable_name in os.environ:
        os.environ[variable_name] = ""
    if isinstance(directory,Iterable) and not isinstance(directory,unicode):
        directories=list(directory)
    else:
        directories=[directory]
    toappend = []
    for _dir in directories:
        if not _dir in os.environ[variable_name]:
            toappend.append(_dir)
    os.environ[variable_name] = (
        os.pathsep.join(toappend)+os.pathsep+os.environ[variable_name])
    ## to clever in my opinion, but maybe it depends on it
    if variable_name == "PYTHONPATH":
        sys.path.insert(0,directory)

def get_lib_dir():
    return 'lib'

def set_env(config, args={},silent=False):
    """Add to the PATH-variables modules specific paths and set all other left
    environment variables specific to the salome application

    :args: dict containing additional agrs, see the source code to get a clue
            what we support here
    :modules_list: list of modules which need to be loaded
    :modules_config: a tuple of (name,module_config) of the module
            configurations
    """
    # source a shell script
    if 'env_sh' in config:
        source_shell_script(config['env_sh'])
    module_root_dirs = set()
    module_resources = set()
    # smesh_setenv assumes it is defined already
    add_path('','SalomeAppConfig')
    for module, module_config in config['modules'].items():
        os.environ['%s_ROOT_DIR'%module] = module_config['root']
        module_root_dirs.add(module_config['root'])
        module_resources.add(module_config['resources'])
        if sys.platform == "win32":
            add_path(module_config['lib'],"PATH")
        else:
            add_path(module_config['lib'],"LD_LIBRARY_PATH")
        add_path(module_config['bin'],"PATH")
        # add lib before site-packages to load script instead of dll if any
        # (win32 platform)
        add_path(module_config['bin'],"PYTHONPATH")
        add_path(module_config['lib'],"PYTHONPATH")
        add_path(module_config['site-packages'],"PYTHONPATH")
        add_path(module_config['shared_modules'],"PYTHONPATH")

        # set environment by modules from the list
        try:
            mod = __import__(module.lower()+"_setenv")
            mod.set_env([])
        except ImportError:
            pass
        except Exception as e:
            pass
            #import traceback
            #print('failed to import {0}_setenv: {1}'.format(module.lower(),e))
            #traceback.print_exc()

    if os.getenv('SALOME_BATCH') == None:
        os.putenv('SALOME_BATCH','0')
    # probably needed, i don't know
    os.environ["SALOMEPATH"]=os.pathsep.join(module_root_dirs)
    # set trace environment variable
    if not os.environ.has_key("SALOME_trace"):
        os.environ["SALOME_trace"]="local"
    if args.get('logfile'):
        os.environ["SALOME_trace"]="file:"+args['logfile']
    if args.get('logger'):
        os.environ["SALOME_trace"]="with_logger"
    if args.get('user_catalog'):
        os.environ['USER_CATALOG_RESOURCES_FILE'] = args['user_catalog']
    elif 'user_catalog' in config:
        os.environ['USER_CATALOG_RESOURCES_FILE'] = config['user_catalog']
    else:
        os.environ['USER_CATALOG_RESOURCES_FILE'] = '/home/martin/.config/salome/CatalogResources.xml'
    # set resources variables if not yet set
    os.environ["CSF_SALOMEDS_ResourcesDefaults"] = config['modules']['KERNEL']['resources']
    # list of all resources
    add_path(module_resources,'SalomeAppConfig')
    if 'env' in config:
        for key,val in config['env'].items():
            add_path(val,key)

def set_env_omniorb(host,port,omniorb_userpath=None):
    if not omniorb_userpath:
        omniorb_userpath = os.path.join(getCacheDir(),'omniORB')
    os.environ['OMNIORB_USER_PATH'] = omniorb_userpath
    os.environ['OMNIORB_CONFIG'] = os.path.join(
        os.environ['OMNIORB_USER_PATH'],'omniORB_{0}_{1}.cfg'.format(host,port))
    os.environ['NSPORT'] = str(port)
    os.environ['NSHOST'] = host

def source_shell_script(path):
    pipe = subprocess.Popen(
        ". %s; env"%path, stdout=subprocess.PIPE,shell=True)
    data = pipe.communicate()[0]
    env = dict((line.split("=", 1) for line in data.splitlines()))
    os.environ.update(env)
