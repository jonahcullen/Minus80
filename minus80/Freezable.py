#!/usr/bin/env python3
import re
import tempfile

import bcolz as bcz
import os as os
import numpy as np
import pandas as pd

from contextlib import contextmanager
from shutil import rmtree as rmdir

from .Config import cf
from .SQLiteDict import sqlite_dict
from .Tools import guess_type

try:
    import apsw as lite
except ModuleNotFoundError as e:
    from .Tools import install_apsw
    install_apsw()
    import apsw as lite


__all__ = ['Freezable']


class relational_db(object):
    def __init__(self, basedir):
        self.filename = os.path.expanduser(
            os.path.join(basedir,'db.sqlite')        
        )
        self.db = lite.Connection(self.filename)

    def cursor(self):
        return self.db.cursor()

    @contextmanager
    def bulk_transaction(self):
        '''
            This is a context manager that handles bulk transaction.
            i.e. this context will handle the BEGIN, END and appropriate
            ROLLBACKS.

            Usage:
            >>> with x._bulk_transaction() as cur:
                     cur.execute('INSERT INTO table XXX VALUES YYY')
        '''
        cur = self._db.cursor()
        cur.execute('PRAGMA synchronous = off')
        cur.execute('PRAGMA journal_mode = memory')
        cur.execute('SAVEPOINT m80_bulk_transaction')
        try:
            yield cur
        except Exception as e:
            cur.execute('ROLLBACK TO SAVEPOINT m80_bulk_transaction')
            raise e
        finally:
            cur.execute('RELEASE SAVEPOINT m80_bulk_transaction')

    def query(self,q):
        cur = self._db.cursor().execute(q)
        names = [x[0] for x in cur.description]
        rows = cur.fetchall()
        result = pd.DataFrame(rows,columns=names)
        return result




class Freezable(object):

    '''
    Freezable is an base class. Things that inherit from Freezable can
    be loaded and unloaded from the Minus80.

    A freezable object is a persistant object that lives in a known directory
    aimed to make expensive to build objects and databases loadable from
    new runtimes.

    The three main things that a Freezable object supplies are:
    * access to a sqlite database (relational records)
    * access to a bcolz databsase (columnar/table data)
    * access to a persistant key/val store
    * access to named temp files

    '''

    def __init__(self, name, parent=None, basedir=None):
        '''
        Initialize the Freezable Object.

        Parameters
        ----------
        name : str
            The name of the frozen object.
        parent: Freezable object or None
            The parent object
        '''
        # Set the m80 name
        self._m80_name = name
        # Set the m80 dtype
        self._m80_dtype = guess_type(self)
      
        # default to the basedir in the config file
        if basedir is None:
            basedir = cf.options.basedir
        # Set up our base directory
        if parent is None:
            # set as the top level basedir as specified in the config file
            self._m80_basedir = os.path.join(
                basedir,
                'databases',
                f'{self._m80_dtype}.{self._m80_name}'
            )
            self._m80_parent = None
        else:
            # set up the basedir to be within the parent basedir
            self._m80_basedir = os.path.join(
                parent._m80_basedir,
                f'{self._m80_dtype}.{self._m80_name}'
            )
            self._m80_parent = parent
            self._m80_parent._m80_add_child(self)
        # Create the base dir
        os.makedirs(self._m80_basedir,exist_ok=True)

        # Get a handle to the sql database
        self._m80db = relational_db(self.basedir)
        # Set up a table
        self._m80_dict = sqlite_dict(self._db) 

    @staticmethod
    def _tmpfile(*args, **kwargs):
        # returns a handle to a tmp file
        return tempfile.NamedTemporaryFile(
            'w',
            dir=os.path.expanduser(
                os.path.join(
                    # use the top level basedir
                    cf.options.basedir,
                    "tmp"
                )
            ),
            **kwargs
        )

    def _get_dbpath(self, extension, create=False):
        '''
        Get the path to database files

        Parameters
        ----------
        '''
        path = os.path.expanduser(
            os.path.join(
                self._basedir,
                f'{extension}'
            )
        )
        if create:
            os.makedirs(path,exist_ok=True)
        return path







