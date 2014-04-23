#!/usr/bin/env python2
import os
import sys
import shutil
import subprocess
import socket
import select
import logging
import datetime
import time
from omniORB import CORBA
from lxml import etree
from opster import command,dispatch
import CosNaming
import glob

logger = logging.getLogger('salome')
logger.setLevel(logging.DEBUG)
stream_handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
stream_handler.setFormatter(formatter)
logger.addHandler(stream_handler)

HOST = '127.0.0.1'
os.environ['OMNIORB_USER_PATH'] = '/home/martin/omniORB/'
LOGFILE = '/home/martin/mytestlogfile.log'

def set_omniorb_env(host,port):
    os.environ['OMNIORB_CONFIG'] = os.path.join(
        os.environ['OMNIORB_USER_PATH'],'omniORB_{0}_{1}.cfg'.format(host,port))
    os.environ['NSPORT'] = str(port)
    os.environ['NSHOST'] = host

def port_free(host,port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # if it was closed previously see: http://stackoverflow.com/a/4466035
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((host,port))
    sock.close()
    return True

def add_path(directory, variable_name):
    """Function helper to add environment variables"""
    if not variable_name in os.environ:
        os.environ[variable_name] = ''
    os.environ[variable_name] += os.pathsep + directory
    if variable_name == "PYTHONPATH":
        sys.path.append(directory)

def set_paths(modules_list,modules_root_dir):
    salome_subdir = 'salome'
    python_version="python%d.%d" % sys.version_info[0:2]
    modules_root_dir_list = []
    for module in modules_list :
        if module in modules_root_dir:
            module_root_dir = modules_root_dir[module]
            if module_root_dir not in modules_root_dir_list:
              modules_root_dir_list[:0] = [module_root_dir]
            add_path(os.path.join(module_root_dir,'lib',salome_subdir),
                    "LD_LIBRARY_PATH")
            add_path(os.path.join(module_root_dir,"bin",salome_subdir),
                     "PATH")
            add_path(os.path.join(module_root_dir,"bin",salome_subdir),
                     "PYTHONPATH")
            # add lib before site-packages to load script instead of dll if any (win32 platform)
            add_path(os.path.join(module_root_dir,'lib',salome_subdir),
                     "PYTHONPATH")
            add_path(os.path.join(module_root_dir,'lib',
                                  python_version,"site-packages",
                                  salome_subdir),
                     "PYTHONPATH")
            import platform
            if platform.machine() == "x86_64":
                add_path(os.path.join(module_root_dir,"lib64",
                                      python_version,"site-packages",
                                      salome_subdir),
                         "PYTHONPATH")
                pass
            add_path(os.path.join(module_root_dir,'lib',
                                  python_version,"site-packages",
                                  salome_subdir,
                                  "shared_modules"),
                     "PYTHONPATH")

            # set environment by modules from the list
            try:
                mod=__import__(module.lower()+"_setenv")
                mod.set_env(args)
            except:
                pass
    os.environ["SALOMEPATH"]=":".join(modules_root_dir_list)

def set_env(root_salome):
    os.environ['USER_CATALOG_RESOURCES_FILE'] = '/home/martin/.config/salome/CatalogResources.xml'
    MODULES = {}
    for x in os.listdir(os.path.join(root_salome,'modules')):
        if os.path.isdir(os.path.join(root_salome,'modules',x)):
            name = x.split('_')[0]
            root = os.path.join(root_salome,'modules',x)
            resources = os.path.join(
                root,'share','salome','resources',name.lower())
            MODULES[name] = {
                'root':root,
                'bin':os.path.join(root,'bin','salome'),
                'resources':resources,
                #if not name.lower().endswith('plugin'):
                'catalog':os.path.join(resources,'%sCatalog.xml'%name),
            }
            os.environ['%s_ROOT_DIR'%name] = root

    # SMESH expects a environment variable describing the meshers, lets create
    # it
    os.environ['SMESH_MeshersList'] = ':'.join(get_meshers(MODULES))
    # list of all resources
    os.environ['SalomeAppConfig'] = ':'.join([v['resources'] for v in MODULES.values()])
    set_paths(MODULES.keys(),{x:v['root'] for x,v in MODULES.items()})
    return MODULES

def get_meshers(modules):
    meshers = []
    for key,val in modules.items():
        for xmlpath in glob.glob(os.path.join(val['resources'],'*.xml')):
            try:
                doc = etree.parse(xmlpath)
                gr = doc.find('meshers-group')
                if gr != None:
                    meshers.append(gr.get('resources'))
            except etree.XMLSyntaxError as e:
                pass
    return meshers


@command()
def connect_to_session(host=('h',HOST,'specify the host machine'),
                  port=('p',2815,'specify the port')):
    set_omniorb_env(host,port)
    MODULES = set_env('/opt/salome')
    os.execvp('/usr/bin/zsh',['/usr/bin/zsh','-c','ipython2'])

def start_omninames(host,port):
    port_free(host,port)
    logdir = '/tmp/logs/omniNames_{0}'.format(port)
    try:
        shutil.rmtree(logdir)
    except:
        pass
    os.makedirs(logdir)

    # in the cfg it is important that the line
    # InitRef = NameService=corbaname::mortbauer:2815
    # points to the correct host and port
    omninames = subprocess.Popen([
        'omniNames',
        '-start',str(port),
        '-logdir', logdir,
        '-errlog', os.path.join(logdir,'omniNameErrors.log'),
    ],stdout=subprocess.PIPE,stderr=subprocess.PIPE)

    conffile = os.environ['OMNIORB_CONFIG']
    with open(conffile,'w') as f:
        f.write('InitRef = NameService=corbaname::{0}:{1}\n'.format(host,port))
        f.write('giopMaxMsgSize = 2097152000 # 2 GBytes\n')
        f.write('traceLevel = 0 # critical errors only\n')
    return omninames,conffile,logdir

def start_notifd(channelfile):
    notifd = subprocess.Popen([
        'notifd','-c', channelfile,
        '-DFactoryIORFileName=/tmp/martin_rdifact.ior',
        '-DChannelIORFileName=/tmp/martin_rdichan.ior',
        '-DReportLogFile=/tmp/martin_notifd.report',
        '-DDebugLogFile=/tmp/martin_notifd.debug',
    ],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    return notifd

def start_salome_launcher_service(modules,catalogs,rootsdir):
    salome_launcher_service = subprocess.Popen([
        os.path.join(rootsdir['KERNEL']['bin'],'SALOME_LauncherServer'),
        '--with', 'Registry', '(', '--salome_session', 'theSession', ')',
        '--with', 'ModuleCatalog', '(', '-common', '::'.join(catalogs), ')',
        '--with', 'SALOMEDS', '(', ')', '--with', 'Container', '(', 'FactoryServer', ')',
    ],stdout=subprocess.PIPE,stderr=subprocess.PIPE,bufsize=1)
    return salome_launcher_service

def start_salome_session_server(modules,catalogs,rootsdir):
    salome_session_server = subprocess.Popen([
        os.path.join(rootsdir['GUI']['bin'],'SALOME_Session_Server'),
        '--with', 'Registry', '(', '--salome_session', 'theSession', ')',
        '--with', 'ModuleCatalog',
        '(', '-common','::'.join(catalogs), ')',
        '--with', 'SALOMEDS', '(', ')',
        '--with', 'Container', '(', 'FactoryServer', ')',
        'CPP', 'GUI', 'SPLASH',
        '--modules ({0})'.format(':'.join(modules)),
    ],stdout=subprocess.PIPE,stderr=subprocess.PIPE,bufsize=1)
    return salome_session_server

def start_salome_connection_manager(modules,catalogs,rootsdir):
    salome_connection_manager = subprocess.Popen([
        os.path.join(rootsdir['KERNEL']['bin'],'SALOME_ConnectionManagerServer'),
    ],stdout=subprocess.PIPE,stderr=subprocess.PIPE,bufsize=1)
    return salome_connection_manager

def start_salome_logger_server(rootsdir,logfile):
    salome_logger_server = subprocess.Popen([
        os.path.join(rootsdir['KERNEL']['bin'],'SALOME_Logger_Server'),logfile,
    ],stdout=subprocess.PIPE,stderr=subprocess.PIPE,bufsize=1)
    return salome_logger_server

@command()
def start_session(host=('h',HOST,'specify the host machine'),
                  port=('p',2815,'specify the port')):
    MODULES = set_env('/opt/salome')
    set_omniorb_env(host,port)
    os.environ['LD_LIBRARY_PATH'] = os.pathsep.join(
        ('/usr/lib/paraview-4.1/','/opt/boost-1.52/lib/',os.getenv('LD_LIBRARY_PATH')))

    channelfile = os.path.join(
        MODULES['KERNEL']['root'],'share/salome/resources/kernel/channel.cfg')
    toload = []
    for x in MODULES:
        if x.startswith('KERNEL') or x.startswith('GUI'):
            continue
        toload.append(x.split('_')[0])
    catalogs = [v['catalog'] for v in MODULES.values()]

    omninames,confile,logdir = start_omninames(host,port)
    notifd = start_notifd(channelfile)
    #salome_logger = start_salome_logger_server(
        #MODULES,LOGFILE)

    processes = [
        omninames,notifd,
        start_salome_launcher_service(toload,catalogs,MODULES),
        start_salome_session_server(toload,catalogs,MODULES),
        start_salome_connection_manager(toload,catalogs,MODULES),
    ]

    import Engines
    import SALOME
    import SALOMEDS
    import SALOME_ModuleCatalog
    import SALOME_Session_idl

    run = True

    poller = select.epoll()
    fds = {}
    for proc in processes:
        poller.register(proc.stdout, select.EPOLLHUP)
        fds[proc.stdout.fileno()] = proc.stdout

    print('salome running on {0}:{1}'.format(host,port))
    try:
        while run:
            for fd,flags in poller.poll(timeout=1):
                run = False
    except KeyboardInterrupt:
        print("received interrupt, shutting done")
    finally:
        for i,proc in enumerate(processes):
            proc.kill()
            proc.wait()
            err = proc.stderr.read()
            if err:
                print(err)
        for path in [confile,logdir]:
            if os.path.isfile(path):
                os.remove(path)
            elif os.path.isdir(path):
                shutil.rmtree(path)
    return

def resolve(host,port):
    set_omniorb_env(host,port)
    orb = CORBA.ORB_init()
    obj = orb.resolve_initial_references("NameService")
    rootContext = obj._narrow(CosNaming.NamingContext)
    obj = rootContext.resolve("Logger")

if __name__ == '__main__':
    dispatch()

