"""
Utility functions to push and pull data from WebDav storage (WebDav API to
dCache offered by SURFsara). adapted from webdav3client. Due to unexpected
behaviour of Client.list() method no use is made of higher level methods (push,
pull) provided.
"""

import pathlib
import os
import shutil
from webdav3.client import Client as wd3client
from webdav3.exceptions import *
from lc_macro_pipeline.utils import check_path_exists, check_file_exists, \
    check_dir_exists, get_args_from_configfile, shell_execute_cmd
#from utils import check_path_exists, check_file_exists, \
#    check_dir_exists, get_args_from_configfile, shell_execute_cmd

def get_wdclient(options=None):
    """
     get webdav

     :param options: specification of options for the client. Either as
                     path to configuration file (str) or a dict
    """
    if isinstance(options,str):
        check_file_exists(options,should_exist=True)
        options = get_options_from_file(options)

    elif isinstance(options,dict):
        pass
    else:
        raise TypeError('unrecognized type {} for client \
                         options'.format(type(options)))
    check_options(options)
    wdclient = wd3client(options)
    return wdclient


def get_options_from_file(options):
    """
    read webdav client option from configuation file. Expects presence of
    an authentication file with user/pwd details

    :param options: filepath of configuration file
    """
    args = get_args_from_configfile(options)
    if 'authenticationfile' in args.keys():
        check_file_exists(args['authenticationfile'],should_exist=True)
        authentication = get_args_from_configfile(args['authenticationfile'])
        args.pop('authenticationfile',None)
        args.update(authentication)
    return args


def check_options(options):
    if not isinstance(options,dict):
        print('options must be a dictionary at this stage.')
        raise TypeError(options)

    keys = options.keys()
    failure = False
    if 'webdav_login' not in keys:
        print('missing "webdav_login" key. \
               Please note that if you are using \
               an authentication file the arguments \
               must be specified there.' )
        failure = True
    if 'webdav_password' not in keys:
        print('missing "webdav_password" key.\
               please note that if you are using \
               an authentication file the arguments \
               must be specified there.' )
        failure = True
    if 'webdav_hostname' not in keys:
        print('missing "webdav_password" key.')
        failure = True

    if failure:
        print('Options specified for Webdav client insufficient to establish client.')
        raise RuntimeError




def push_file_to_remote(wdclient,local_origin,remote_destination,file):
    """
    upload file to remote

    :param wdclient: instance of webdav client
    :param local_origin: directory of file on local fs
    :param remote_destination: target directory of file on remote fs
    :param file: file name
    """
    if not isinstance(file,str):
        print('Expected type str but received type {}'.format(type(file)))
        raise TypeError

    remote_path_to_file = os.path.join(remote_destination,file)
    local_path_to_file = os.path.join(local_origin,file)

    if wdclient.check(remote_destination) == True:
        try:
            wdclient.upload_sync(remote_path_to_file,local_path_to_file)
        except WebDavException as exception:
            print('Failed to upload {} to \
                                            remote destination'.format(file))
            raise
    else:
        print("remote parent directory {} does not exist ".format(remote_destination))
        raise RemoteResourceNotFound(remote_path_to_file)


def pull_file_from_remote(wdclient,local_destination,remote_origin,file):
    """
    download file from remote

    :param wdclient: instance of webdav client
    :param local_destination: target directory of file on local fs
    :param remote_origin: parent directory of file on remote fs
    :param file: file name
    """
    if not isinstance(file,str):
        print('Expected type str but received type {}'.format(type(file)))
        raise TypeError

    remote_path_to_file = os.path.join(remote_origin,file)
    local_path_to_file = os.path.join(local_destination,file)

    try:
        wdclient.download_file(remote_path_to_file,local_path_to_file)
    except WebDavException as exception:
        print('failed to download {} from remote'.format(file))
        raise



"""
this currently does not work due to issues with the parsing of the rmote fs exposed by SURFsara.

"""
#def pull_directory_from_remote(wdclient,local_dir,remote_dir,mode='pull'):
#    """
#    pull directory from remote to local fs. This can be done as a full download
#    or a (one-way) sync.

#    :param wdclient: instance of webdav client
#    :param local_dir: local directory to be synced or created
#    :param remote_dir: remote directory to be pulled or downloaded
#    :param mode: 'pull': sync directory ; 'download': download
#    """
#    if mode == 'pull':
#        if not os.path.exists(local_dir):
#            shell_execute_cmd('mkdir '+ local_dir)
#        elif os.path.isfile(local_dir):
#            raise FileExistsError(local_dir)
#        else :
#            pass
#
#        try:
#            wdclient.pull(remote_directory=remote_dir,local_directory=local_dir)
#        except WebDavException as exception:
#            print('Failed to pull {} to \
#                                    {}'.format(remote_dir,local_dir))
#            raise
#
#    elif mode == 'download':
#        p =pathlib.Path(local_dir)
#        if not p.parent.exists():
#            print('parent directory of local_dir does not exist! Aborting...')
#            raise FileNotFoundError(p.parent)
#
#        try:
#            wdclient.download_sync(remote_dir,local_dir)
#        except WebDavException as exception:
#            print('Failed to download {} to \
#                                    {}'.format(remote_dir,local_dir))
#            raise


def pull_directory_from_remote(wdclient,local_dir,remote_dir):
    """
    pull all files in a directory to local system.
    WILL FAIL if directory exists on local fs

    :param wdclient: instance of webdav client
    :param local_dir: local directory to be downloaded to/created
    :param remote_dir: remote directory to be downloaded
    """

    if os.path.exists(local_dir):
        print('A file or directory already exists with this name')
        raise FileExistsError(local_dir)

    try:
        wdclient.check(remote_dir)
    except WebDavException as exception:
        print('failed to ascertain existance of remote directory')
        raise

    records = wdclient.list(remote_dir)
    records=records[1:]

    os.makedirs(local_dir)

    for record in records:
        rpath = os.path.join(remote_dir,record)
        lpath = os.path.join(local_dir,record)
        if wdclient.is_dir(rpath):
            try:
                pull_directory_from_remote(wdclient,lpath,rpath)
            except WebDavException as exception:
                print('failed to recursively pull {}'.format(record))
                raise
        else:
            try:
                pull_file_from_remote(wdclient,local_dir,remote_dir,record)
            except WebDavException as exception:
                print('failed to pull {} from {}'.format(record,remote_dir))
                raise



"""
unclear why push behaviour changed
"""
#def push_directory_to_remote(wdclient,local_dir,remote_dir,mode='push'):
#    """
#    push directory from local fs to remote. This can be done as a full upload
#    or a (one-way) sync.
#
#    :param wdclient: instance of webdav client
#    :param local_dir: local directory to be synced or uploaded
#    :param remote_dir: remote directory to be synced or uploaded
#    :param mode: 'push': sync directory ; 'upload': upload
#    """
#    if not os.path.isdir(local_dir):
#        print('{} is not a directory'.format(local_dir))
#        raise NotADirectoryError(local_dir)
#
#        if wdclient.check(remote_dir) == False:
#            try:
#                wdclient.mkdir(remote_dir)
#            except WebDavException as exception:
#                print('failed to create required remote directory {}'.format(remote_dir))
#                raise
#        try:
#            wdclient.push(remote_directory=remote_dir,local_directory=local_dir)
#        except WebDavException as exception:
#            print('Failed to push {} to \
#                                    {}'.format(local_dir,remote_dir))
#            raise
#
#    elif mode == 'upload':
#        try:
#            wdclient.upload_sync(remote_dir,local_dir)
#        except WebDavException as exception:
#            print('Failed to upload {} to \
#                                    {}'.format(local_dir,remote_dir))
#            raise


def push_directory_to_remote(wdclient,local_dir,remote_dir):
    """
    push directory from local fs to remote

    :param wdclient: instance of the wedav client
    :param local_dir: directory on local fs to be pushed
    :param remote_dir: target directory on remote fs
    """

    if wdclient.check(remote_dir) == False:
        try:
            wdclient.mkdir(remote_dir)
        except WebDavException as exception:
            print('failed to create remote directory')
            raise FileNotFoundError
    else:
        if wdclient.is_dir(remote_dir) == True:
            pass
        else:
            print('A record exits at {} on the remote fs which is not a directory.')
            raise FileExistsError

    lrecords = os.listdir(local_dir)

    for lrecord in lrecords:
        lpath = os.path.join(local_dir, lrecord)
        rpath = os.path.join(remote_dir,lrecord)

        if os.path.isdir(lpath):
            push_directory_to_remote(wdclient,lpath,rpath)
        else:
            if wdclient.check(rpath):
                wdclient.clean(rpath)  #remove remote file if present
            push_file_to_remote(wdclient,local_dir,remote_dir,lrecord)




def purge_local(local_record):
    """
    remove record from local file system

    :param local_record : full path of local_record
    """
    check_path_exists(local_record,should_exist=True)
    shutil.rmtree(local_record)