#  -*- coding: iso-8859-1 -*-
# modified version of the original salome_utils.py from  the salome-kernel
# module removed the most crazy functions

import os

__all__ = [
    'getORBcfgInfo',
    'getHostFromORBcfg',
    'getPortFromORBcfg',
    'getUserName',
    'getHostName',
    'getShortHostName',
    'getAppName',
    'getPortNumber',
    'getTmpDir',
    'getHomeDir',
    'generateFileName',
    'getCacheDir',
    'getConfigDir',
    ]

def _try_bool( arg ):
    """
    Check if specified parameter represents boolean value and returns its value.
    String values like 'True', 'TRUE', 'YES', 'Yes', 'y', 'NO', 'false', 'n', etc
    are supported.
    If <arg> does not represent a boolean, an exception is raised.
    """
    import types
    if type( arg ) == types.BooleanType  :
        return arg
    elif type( arg ) == types.StringType  :
        v = str( arg ).lower()
        if   v in [ "yes", "y", "true"  ]: return True
        elif v in [ "no",  "n", "false" ]: return False
        pass
    raise Exception("Not boolean value")

def verbose():
    return False

def setVerbose():
    pass

def getORBcfgInfo():
    """
    Get omniORB current configuration.
    Returns a list of three values: [ orb_version, host_name, port_number ].

    The information is retrieved from the omniORB configuration file defined
    by the OMNIORB_CONFIG environment variable.
    If omniORB configuration file can not be accessed, a list of three empty
    strings is returned.
    """
    import re
    ret = [ "", "", "" ]
    regvar = re.compile( "(ORB)?InitRef.*corbaname::(.*):(\d+)\s*$" )
    try:
        with open(os.getenv( "OMNIORB_CONFIG"),'r') as f:
            lines = f.readlines()
    except:
        return ret
    for line in lines:
        m = regvar.match(line)
        if m:
            if m.group(1) is None:
                ret[0] = "4"
            else:
                ret[0] = "3"
            ret[1] = m.group(2)
            ret[2] = m.group(3)
            break
    return ret

def getHostFromORBcfg():
    """
    Get current omniORB host.
    """
    return getORBcfgInfo()[1]

def getPortFromORBcfg():
    """
    Get current omniORB port.
    """
    return getORBcfgInfo()[2]

def getUserName():
    """
    Get user name:
    1. try USER environment variable
    2. if fails, return 'unknown' as default user name
    """
    return os.getenv("USER", "unknown" ) # 'unknown' is default user name

def getHostName():
    """
    Get host name:
    1. try socket python module gethostname() function
    2. if fails, try HOSTNAME environment variable
    3. if fails, try HOST environment variable
    4. if fails, return 'unknown' as default host name
    """
    try:
        import socket
        host = socket.gethostname()
    except:
        host = None
    if not host: host = os.getenv("HOSTNAME")
    if not host: host = os.getenv("HOST")
    if not host: host = "unknown"           # 'unknown' is default host name
    return host

def getShortHostName():
    """
    Get short host name:
    1. try socket python module gethostname() function
    2. if fails, try HOSTNAME environment variable
    3. if fails, try HOST environment variable
    4. if fails, return 'unknown' as default host name
    """
    try:
        return getHostName().split('.')[0]
    except:
        pass
    return "unknown"           # 'unknown' is default host name

def getAppName():
    """
    Get application name:
    1. try APPNAME environment variable
    2. if fails, return 'SALOME' as default application name
    """
    return os.getenv( "APPNAME", "SALOME" ) # 'SALOME' is default user name

def getPortNumber(use_default=True):
    """
    Get current naming server port number:
    1. try NSPORT environment variable
    2. if fails, try to parse config file defined by OMNIORB_CONFIG environment
       variable
    3. if fails, return 2809 as default port number (if use_default is True) or
       None (id use_default is False)
    """
    try:
        return int( os.getenv( "NSPORT" ) )
    except:
        try:
            port = int( getPortFromORBcfg() )
            if port is not None:
                return port
        except:
            if use_default:
                return 2809 # '2809' is default port number
            else:
                return None

def getHomeDir():
    """
    Get home directory.
    """
    import sys
    if sys.platform == "win32":
        # for Windows the home directory is detected in the following way:
        # 1. try USERPROFILE env variable
        # 2. try combination of HOMEDRIVE and HOMEPATH env variables
        # 3. try HOME env variable
        # TODO: on Windows, also GetUserProfilehomedirectoryW() system function
        # might be used
        homedir = os.getenv("USERPROFILE")
        if not homedir and os.getenv("HOMEDRIVE") and os.getenv("HOMEPATH"):
            return os.path.join(os.getenv("HOMEDRIVE"),os.getenv("HOMEPATH"))
        elif not homedir:
            return os.getenv("HOME")
        else:
            return homedir
    else:
        # for Linux: use HOME variable
        return os.getenv("HOME")

def getTmpDir():
    """
    Get directory to be used for the temporary files.
    """
    import sys
    if sys.platform == "win32":
        tmp = os.getenv("TMP")
        if tmp:
            return tmp
        else:
            return os.getenv('TEMP')
    else:
        tmp = os.getenv('TMPDIR')
        if tmp:
            return tmp
        else:
            return '/tmp'

def generateFileName(directory, prefix = None, suffix = None, extension = None,
                      unique=False,separator="_", hidden=False, **kwargs ):
    """
    Generate file name by sepecified parameters. If necessary, file name
    can be generated to be unique.

    Parameters:
    - directory       : directory path
    - prefix    : file prefix (not added by default)
    - suffix    : file suffix (not added by default)
    - extension : file extension (not added by default)
    - unique    : if this parameter is True, the unique file name is generated:
    in this case, if the file with the generated name already exists
    in the <directory> directory, an integer suffix is added to the end of the
    file name. This parameter is False by default.
    - separator : separator of the words ('_' by default)
    - hidden    : if this parameter is True, the file name is prepended by . (dot)
    symbol. This parameter is False by default.

    Other keyword parameters are:
    - with_username : 'add user name' flag/option:
      * boolean value can be passed to determine user name automatically
      * string value to be used as user name
    - with_hostname : 'add host name' flag/option:
      * boolean value can be passed to determine host name automatically
      * string value to be used as host name
    - with_port     : 'add port number' flag/option:
      * boolean value can be passed to determine port number automatically
      * string value to be used as port number
    - with_app      : 'add application name' flag/option:
      * boolean value can be passed to determine application name automatically
      * string value to be used as application name
    All <with_...> parameters are optional.
    """
    import sys
    supported = [ 'with_username', 'with_hostname', 'with_port', 'with_app' ]
    filename = []
    if sys.platform == 'win32':
        hidden_prefix = '_'
    else:
        hidden_prefix = '.'
    # separator
    if separator is None:
        separator = ""
    else:
        separator = str( separator )
    # prefix (if specified)
    if prefix is not None:
        filename.append( str( prefix ) )
    ### process supported keywords
    for kw in kwargs:
        if kw == 'with_username':
            # auto user name ?
            if _try_bool(kwargs[kw]):
                filename.append(getUserName())
            else:
                # user name given as parameter
                filename.append(kwargs[kw])
        elif kw == 'with_hostname':
            # auto host name ?
            if _try_bool( kwargs[kw] ):
                filename.append(getShortHostName())
            else:
                # host name given as parameter
                filename.append( kwargs[kw] )
        elif kw == 'with_port':
            # auto port number ?
            if _try_bool( kwargs[kw] ):
                filename.append( str( getPortNumber()))
            else:
                # port number given as parameter
                filename.append( str( kwargs[kw] ) )
        elif kw == 'with_app':
            # auto application name ?
            if _try_bool( kwargs[kw] ):
                filename.append( getAppName() )
            else:
                # application name given as parameter
                filename.append( kwargs[kw] )
        else:
            pass
    # suffix (if specified)
    if suffix is not None:
        filename.append( str( suffix ) )
    # raise an exception if file name is empty
    if not filename:
        raise ValueError("Empty file name")
    #
    if extension is not None and extension.startswith("."):
        extension = extension[1:]
    def normalize(name):
        if hidden:
            name = hidden_prefix + name
        if extension:
            name += "." + str( extension )
        return os.path.normpath(os.path.join( directory, name))

    name = normalize(separator.join(filename))
    if unique:
        # create unique file name
        index = 0
        while os.path.exists(name):
            index = index + 1
            name = normalize(
                separator.join(
                    filename)+separator+str(index))
    return name
def getConfigDir():
    import sys
    if sys.platform == "win32":
        return os.getenv('LOCALAPPDATA')
    else:
        return os.getenv('XDG_CONFIG_HOME','.config')

def getCacheDir():
    import sys
    if sys.platform == "win32":
        return os.getenv('LOCALAPPDATA')
    else:
        return os.getenv('XDG_CACHE_HOME','.cache')

def uniteFiles( src_file, dest_file ):
    """
    Unite contents of the source file with contents of the destination file
    and put result of the uniting to the destination file.
    If the destination file does not exist then the source file is simply
    copied to its path.

    Parameters:
    - src_file  : absolute path to the source file
    - dest_file : absolute path to the destination file
    """
    import os

    if not os.path.exists( src_file ):
        return

    if os.path.exists( dest_file ):
        # add a symbol of new line to contents of the destination file (just in case)
        dest = open( dest_file, 'r' )
        dest_lines = dest.readlines()
        dest.close()

        dest_lines.append( "\n" )

        dest = open( dest_file, 'w' )
        dest.writelines( dest_lines )
        dest.close()

        import sys
        if sys.platform == "win32":
            command = "type " + '"' + src_file + '"' + " >> " + '"' + dest_file + '"'
        else:
            command = "cat " + src_file + " >> " + dest_file
            pass
        pass
    else:
        import shutil
        try:
            sutil.copyfile(src_file,dest_file)
        except:
            pass
