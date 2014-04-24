#!/usr/bin/env python2
import os
import sys
import shutil
import subprocess
import socket
import select
import logging
import datetime
import setenv
import time
from omniORB import CORBA
from opster import command,dispatch
import CosNaming
import glob
import json
import signal

logger = logging.getLogger('salome')
logger.setLevel(logging.DEBUG)
stream_handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
stream_handler.setFormatter(formatter)
logger.addHandler(stream_handler)

HOST = '127.0.0.1'
LOGFILE = '/home/martin/mytestlogfile.log'

def test_port(host,port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # if it was closed previously see: http://stackoverflow.com/a/4466035
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((host,port))
    sock.close()
    return True

def save_config(config,configpath):
    with open(configpath,'w') as store:
        json.dump(config,store,sort_keys=True, indent=4)

def read_config(configpath):
    with open(configpath,'r') as store:
        config = json.load(store)
    return config


def start_naming_service(host,port):
    test_port(host,port)
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
    if not os.path.isdir(os.path.split(conffile)[0]):
        os.makedirs(os.path.split(conffile)[0])
    with open(conffile,'w') as f:
        f.write('InitRef = NameService=corbaname::{0}:{1}\n'.format(host,port))
        f.write('giopMaxMsgSize = 2097152000 # 2 GBytes\n')
        f.write('traceLevel = 0 # critical errors only\n')
    return omninames,conffile,logdir

def start_notification_service(channelfile):
    notifd = subprocess.Popen([
        'notifd','-c', channelfile,
        '-DFactoryIORFileName=/tmp/rdifact.ior',
        '-DChannelIORFileName=/tmp/rdichan.ior',
        '-DReportLogFile=/tmp/notifd.report',
        '-DDebugLogFile=/tmp/notifd.debug',
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

def start_salome_session_server(modules,catalogs,rootsdir,services=[]):
    salome_session_server = subprocess.Popen([
        os.path.join(rootsdir['GUI']['bin'],'SALOME_Session_Server'),
        '--with', 'Registry', '(', '--salome_session', 'theSession', ')',
        '--with', 'ModuleCatalog',
        '(', '-common','::'.join(catalogs), ')',
        '--with', 'SALOMEDS', '(', ')',
        '--with', 'Container', '(', 'FactoryServer', ')',
        '--modules ({0})'.format(':'.join(modules)),
    ]+services ,stdout=subprocess.PIPE,stderr=subprocess.PIPE,bufsize=1)
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


@command(usage='PATH_TO_MODULES OUTPUTFILEPATH')
def create_and_save_config_template(modules_path,config_path):
    save_config(setenv.create_config_template(modules_path),config_path)

@command()
def launch_session(config,
                   host=('h',HOST,'specify the host machine'),
                   port=('p',2815,'specify the port'),
                   modules=('m','','specify a list of modules to load'),
                   quiet=('',False,'don\'t print any error messages from salome'),
                   nogui=('',False,'don\'launch gui'),
                   services=('s','CPP,GUI,SPLASH','specify a list of services to load (CPP,GUI,SPLAH)')):
    configuration = read_config(config)
    # by default load all modules
    if not modules:
        modules = configuration['modules'].keys()
    else:
        modules = [x.upper() for x in modules.split(',')]

    # by default load all services
    services = [x.upper() for x in services.split(',')]
    if nogui:
        services = [x for x in services if x != 'GUI']

    # set up the environment
    setenv.set_env_omniorb(host,port)
    setenv.set_env(configuration)

    channelfile = os.path.join(
        configuration['modules']['KERNEL']['resources'],'channel.cfg')

    catalogs = [v['catalog'] for v in configuration['modules'].values()]
    processes = []
    rmfiles = []

    def clean_up():
        for i,proc in enumerate(processes):
            proc.kill()
            proc.wait()
            if not quiet:
                err = proc.stderr.read()
                if err:
                    print(err)
        for path in rmfiles:
            if os.path.isfile(path):
                os.remove(path)
            elif os.path.isdir(path):
                shutil.rmtree(path)

    def signal_handler(signum=None, frame=None):
        ## seems useless, but maybe will need it later so leave it here anyways
        sys.exit(0)

    for sig in [signal.SIGTERM, signal.SIGINT, signal.SIGHUP, signal.SIGQUIT]:
        signal.signal(sig, signal_handler)
    try:
        omninames,confile,logdir = start_naming_service(host,port)
        processes = [omninames]
        rmfiles = [confile,logdir]

        processes.append(start_notification_service(channelfile))
        #salome_logger = start_salome_logger_server(
            #MODULES,LOGFILE)

        processes.append(
            start_salome_launcher_service(
                modules,catalogs,configuration['modules']))
        processes.append(
            start_salome_session_server(
                modules,catalogs,configuration['modules'],services=services))
        processes.append(
            start_salome_connection_manager(
                modules,catalogs,configuration['modules']))

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

    except Exception as e:
        print('sorry, couldn\'t launch because of: {0}'.format(e))
    finally:
        clean_up()
    return

@command()
def connect_session(config,
                    host=('h',HOST,'specify the host machine'),
                    port=('p',2815,'specify the port'),
                    args=('','','specify args')):
    setenv.set_env_omniorb(host,port)
    setenv.set_env(read_config(config))
    if not args:
        os.execvp('/usr/bin/zsh',['/usr/bin/zsh'])
    else:
        os.execvp('/usr/bin/zsh',['/usr/bin/zsh','-c',args])

@command()
def resolve(host=('h',HOST,'specify the host machine'),
                  port=('p',2815,'specify the port')):
    set_env_omniorb(host,port)
    orb = CORBA.ORB_init()
    obj = orb.resolve_initial_references("NameService")
    rootContext = obj._narrow(CosNaming.NamingContext)
    obj = rootContext.resolve("Logger")

if __name__ == '__main__':
    dispatch()

