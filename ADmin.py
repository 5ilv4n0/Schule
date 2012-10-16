#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#  ADmin.py
#  
#  Copyright 2012 Silvano Wegener <silvano@DV8000>
#  
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#  
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#  
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#  MA 02110-1301, USA.
#  
#  


import MySQLdb as _mysql
import sys, json


def makeIntOrUseDefault(value, default):
    try:
        value = int(value)
        return value
    except ValueError:
        return default


class SqlTableAttribute(object):
    def __init__(self, name, typ, autoIncrement=False, isPrimaryKey=False, length=255):
        self.name = name
        self.typ = typ
        self.autoIncrement = autoIncrement
        self.isPrimaryKey = isPrimaryKey
        self.length = length
        self.content = []


    def addValue(self, value):
        if self.isValueBiggerThanLength(value):
            return False
        self.content.append(value)
        return True
        
        
    def isValueBiggerThanLength(self, value):
        maxIntValue = int('9'*self.length)
        if self.typ == 'varchar':
            if len(value) > self.length:
                return True
        elif self.typ == 'int':
            if value > maxIntValue:
                return True
        return False


class SqlTable(object):
    def __init__(self, name):
        self.name = name
        self.attributes = {}
        self.addAttribute('ID', 'int', True, True, 11)
        
    def addAttribute(self, name, typ, autoIncrement=False, isPrimaryKey=False, length=255):
        attribute = SqlTableAttribute(name, typ, autoIncrement, isPrimaryKey, length)
        self.attributes[name] = attribute
        
    def addData(self, **keyWordArgs):
        for key in keyWordArgs:
            if not key in self.attributes.keys():
                print 'Attribute "' + key + '" does not exists in table "' + self.name + '"!'
                return False
        for key in self.attributes.keys():
            if not key in keyWordArgs.keys():
                print 'Attribute "' + key + '" expected!'
                return False
        for key in self.attributes.keys():
            self.attributes[key].addValue(keyWordArgs[key])



class SqlDatabase(object):
    def __init__(self, name):
        self.name = name
        self.tables = {}
        
    def addTable(self, name):
        self.tables[name] = SqlTable(name)
        
    def showDatabase(self):
        database = {}
        for table in self.tables.keys():
            database[table] = {}
            for attribute in self.tables[table].attributes.keys():
                database[table][attribute] = self.tables[table].attributes[attribute].content
        print json.dumps(database, indent=4)





with open('usergroup.json','r') as f:
    userGroup = json.load(f)
    types = userGroup['types']
    users = userGroup['users']
    groups = userGroup['groups']
    

db = SqlDatabase('CrashCom')

db.addTable('ObjektTyp')
db.tables['ObjektTyp'].addAttribute('Type', 'varchar')
for ID, typ in enumerate(types):
    db.tables['ObjektTyp'].addData(ID=ID, Type=typ)

db.addTable('Gruppe')
db.tables['Gruppe'].addAttribute('Name', 'varchar')
for ID, group in enumerate(groups):
    db.tables['Gruppe'].addData(ID=ID, Name=group)

db.addTable('Benutzer')
db.tables['Benutzer'].addAttribute('Name', 'varchar')
for ID, user in enumerate(users):
    db.tables['Benutzer'].addData(ID=ID, Name=user)

db.showDatabase()







class MySQLClient(object):
    def __init__(self, address, port, user, password, databaseName):
        self.address = address
        self.port = makeIntOrUseDefault(port, 3306)
        self.user = user
        self.password = password
        self.databaseName = databaseName


    def connect(self):
        try:
            self.connection = _mysql.connect(host=self.address, port=self.port, user=self.user, passwd=self.password)
            self.createDatabase(self.databaseName)
        except _mysql.Error, error:
            print error
            errorCode = error[0]
            self.byError(errorCode)
            sys.exit(1)


    def createDatabase(self, databaseName):
        self.sqlExecute('create database if not exists', databaseName)


    def sqlExecute(self, *commandParts):
        command = ' '.join(commandParts)
        self.connection.query(command + ';')


    def byError(self, errorCode):
        if errorCode == 0:
            pass
        elif errorCode == 1007:
            print 'Creation Error! Database already exists!'
        elif errorCode == 1045:
            print 'Login failed!'
        elif errorCode == 1049:
            print 'Unknown Database'
        elif errorCode == 1064:
            print 'Syntax Error!'






sql = MySQLClient('localhost', 3306, 'root', 'bbbbbb', 'CrashCom')
sql.connect()














#~ 
#~ user = []
#~ user.append('Dietmar Renzen')
#~ user.append('Peter Klug')
#~ user.append('Ernst Verse')
#~ user.append('Vera Stimmung')
#~ user.append('Dieter Gross')
#~ user.append('Evelyn Schmal')
#~ user.append('Ottfried Kall')
#~ user.append('Tom schmächtle')
#~ user.append('Paul Starke')
#~ user.append('Raimund Reim')
#~ user.append('Dirk Nagel')
#~ user.append('Erwin Schmitz')
#~ user.append('Clara Sommer')
#~ user.append('Herrmann Winter')
#~ user.append('Peter Frühling')
#~ user.append('Carmen Herbst')
#~ user.append('Werner Fassnacht')
#~ user.append('Claudia Jahr')
#~ user.append('Marlies Stunde')
