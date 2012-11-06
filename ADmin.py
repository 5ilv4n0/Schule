#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#  project.py
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
#  AdminPassword = 'Bbbbbb6'

#con.createTable(name='Benutzer', attributes=['UID int 11 primaryKey autoIncrement', 'Name varchar 255', 'Gruppe_GID int 11'], foreignKeys=['Gruppe GID'])


import sys, os, json
import win32com
from pyad import pyad
import MySQLdb as _mysql






def makeIntOrUseDefault(value, defaultValue=0):
    try:
        value = int(value)
        return value
    except ValueError:
        return defaultValue

class MySQLConnection(object):
    def __init__(self, address, port, username, password, databaseName):
        self.address = address
        self.port = makeIntOrUseDefault(port, 3306)
        self.__username = username
        self.__password = password
        self.databaseName = databaseName
        self.__connection = self.connect(self.address,  self.port, self.__username, self.__password)
        self.__tables = {}
        self.history = []

    def connect(self, address, port, username, password):
        try:
            conn = _mysql.connect(host=address, port=port, user=username, passwd=password)
            return conn
        except _mysql.Error, error:
            sqlErrorCode = error[0]
            print self.translateSQLErrorCode(sqlErrorCode)
            sys.exit(1)
        
    def translateSQLErrorCode(self, sqlErrorCode):
        sqlErrorCodes = {}
        sqlErrorCodes[1045] = 'Access denied!'
        sqlErrorCodes[2003] = 'Could not connect to sql server!'        
        return sqlErrorCodes[sqlErrorCode]

    def createDatabase(self, databaseName):
        return self.executeSQL('create database', databaseName)

    def dropDatabase(self, databaseName):
        return self.executeSQL('drop database', databaseName)

    def useDatabase(self, databaseName):
        return self.executeSQL('use', databaseName)

    def createTable(self, **tableParameters):
        try:
            tableName = tableParameters['name']
            attributes = tableParameters['attributes']
            self.__tables[tableName] = {}
        except KeyError:
            return False
        try:
            foreignKeys = tableParameters['foreignKeys']
        except KeyError:
            foreignKeys = []
        foreignKeyParts = []
        attributeNames = []
        for foreignKeyInfo in foreignKeys:
            foreignKeyInfo = foreignKeyInfo.split()
            foreignKeyName = '_'.join(foreignKeyInfo)
            foreignKeyParts.append('foreign key(' + foreignKeyName + ') references ' + foreignKeyInfo[0] + '(' + foreignKeyInfo[1] + ')')
        createTableCommand = []
        createTableCommand.append('create table')
        createTableCommand.append(tableName)
        createTableCommand.append('(')
        attributeCommandParts = []
        for attribute in attributes:
            attribute = attribute.split()
            attributeName = attribute[0]
            attributeNames.append(attributeName)
            attributeType = attribute[1]
            attributeLength = attribute[2]
            attributeIsPrimaryKey = False
            attributeAutoIncrement = False
            if 'primaryKey' in attribute:
                attributeIsPrimaryKey = True
            if 'autoIncrement' in attribute:
                attributeAutoIncrement = True
            attributeCommandPart = attributeName + ' '
            attributeCommandPart += attributeType + '(' + str(attributeLength) + ')'
            if attributeAutoIncrement:
                attributeCommandPart += ' auto_increment'
            if attributeIsPrimaryKey:
                attributeCommandPart += ' primary key'
            attributeCommandParts.append(attributeCommandPart)
        attributeCommandParts.extend(foreignKeyParts)
        createTableCommand.append(', '.join(attributeCommandParts))
        createTableCommand.append(')')
        createTableCommand = ' '.join(createTableCommand)
        self.__tables[tableName]['attributes'] = attributeNames
        return self.executeSQL(createTableCommand)    

    def dropTable(self, tableName):
        return self.executeSQL('drop table', tableName)

    def insertValues(self, **values):
        tableName = values['tableName']
        del values['tableName']
        insertSQLCommandParts = []
        insertSQLCommandParts.append('insert into')
        insertSQLCommandParts.append(tableName)
        insertSQLCommandParts.append('(')
        insertSQLCommandParts.append(','.join(values.keys()))
        insertSQLCommandParts.append(')')
        insertSQLCommandParts.append('values')
        insertSQLCommandParts.append('(')
        newValues = []
        for value in values.values():
            newValues.append('"' + str(value) + '"')
        insertSQLCommandParts.append(','.join(newValues))
        insertSQLCommandParts.append(')')
        command = ' '.join(insertSQLCommandParts)
        return self.executeSQL(command)        

    def getTable(self, tableName):
        return self.executeSQLAndReturn('select * from ' + tableName)

    def executeSQL(self, *commandParts):
        command = ' '.join(commandParts) + ';'
        try:
            self.__connection.query(command)
            returnValue = True
        except _mysql.Error:
            returnValue = False
        historyEntry = ' = '.join((str(command), str(returnValue)))
        self.history.append(historyEntry)
        self.__connection.commit()
        return returnValue
       
    def executeSQLAndReturn(self, *commandParts):
        command = ' '.join(commandParts) + ';'
        cursor = self.__connection.cursor()
        try:
            cursor.execute(command)
            returnList = []
            for entry in cursor:
                returnList.append(entry)
            return returnList
        except _mysql.Error:
            return False    
 
    def addOU(self, ouName, ldapPath=''):
        self.insertValues(tableName='OrganisationsEinheit', Name=ouName, LDAPPfad=ldapPath)

    def addGroup(self, groupName, OUID): 
        self.insertValues(tableName='SicherheitsGruppe', Name=groupName, OrganisationsEinheit_OUID=OUID)
        return True
        
    def addUser(self, userName, *groups):
        newGroups = []
        for groupID in groups:
            newGroups.append(str(groupID))
        newGroups = ','.join(newGroups)
        self.insertValues(tableName='Benutzer', Name=userName, Gruppen=newGroups)

    def __str__(self):
        return json.dumps(self.history, indent=4)


class LDAP(object):
	def __init__(self, mySQLConnection):
		self.mySQLConnection = mySQLConnection
		
	def addUser(self, firstName, lastName, securityGroup, mustChangePassword=True ,description='Ich bin ein Benutzer'):
		ouRoot = pyad.adcontainer.ADContainer.from_dn("DC=IDEALTEC,DC=ORG")
		try:
			ouRoot.create_container('Benutzer')
			ouUsers = pyad.adcontainer.ADContainer.from_dn("OU=Benutzer,DC=IDEALTEC,DC=ORG")
		except:
			return False
		
	def addUsersFromSQL(self):
		for userID, userName, securityGroupID in con.getTable('Benutzer'):
			principalName = self.makeUserPrincipalName(userName)
			#print userName, int(securityGroupID), self.makeSAMAccountName(userName), self.displayName(userName)
			nameSplits = self.splitNames(userName)			
			exAttr = {}
			exAttr['givenName'] = nameSplits[0]
			exAttr['sn'] = nameSplits[1]			
			exAttr['initials'] = nameSplits[0][0] + nameSplits[1][0]
			exAttr['displayName'] = self.displayName(userName)
			exAttr['samAccountName'] = self.makeSAMAccountName(userName)
			#exAttr['nTSecurityDescriptor'] = True
			
			exAttr['description'] = exAttr['displayName'] + ' ist ein Benutzer.'		

			
			user = pyad.aduser.ADUser.create(principalName, ouUsers, password='Changeme123', upn_suffix=None, enable=True, optional_attributes=exAttr)

		

	def makeUserPrincipalName(self, name):
		name = self.splitNames(name)
		return '.'.join(name)
		
	def makeSAMAccountName(self, name):
		name = self.splitNames(name)
		samName = name[0][0] + name[1][:18]
		return samName
		
	def displayName(self, name):
		name = self.splitNames(name)
		return name[1] + ', ' + name[0]

		
	def splitNames(self, name):
		return name.split()



con = MySQLConnection('localhost', 3306, 'root', '', 'CrashCom')
con.dropDatabase('CrashCom')
con.createDatabase('CrashCom')
con.useDatabase('CrashCom')
con.createTable(name='OrganisationsEinheit', attributes=['OUID int 11 primaryKey autoIncrement', 'Name varchar 255', 'LDAPPfad varchar 255'])
con.createTable(name='SicherheitsGruppe', attributes=['SGID int 11 primaryKey autoIncrement', 'Name varchar 255', 'OrganisationsEinheit_OUID int 11'], foreignKeys=['OrganisationsEinheit OUID'])
con.createTable(name='Benutzer', attributes=['UID int 11 primaryKey autoIncrement', 'Name varchar 255', 'Gruppen varchar 255'])
con.addOU('TestOU')

ouRoot = pyad.adcontainer.ADContainer.from_dn("DC=IDEALTEC,DC=ORG")
try:
	ouRoot.create_container('Benutzer')
except:
	pass
	
ouUsers = pyad.adcontainer.ADContainer.from_dn("OU=Benutzer,DC=IDEALTEC,DC=ORG")
print ouUsers

con.addGroup('Geschaetsfuehrung',1)
con.addUser('Dietmar Renzen', 1)

con.addGroup('Schulungsleitung',1)
con.addUser('Peter Klug', 2)

con.addGroup('Schulungspersonal',1)
con.addUser('Dieter Gross', 3)
con.addUser('Evelin Schmal', 3)
con.addUser('Ottfried Kall', 3)
con.addUser('Tom Schmaechtle', 3)
con.addUser('Paul Starke', 3)

con.addGroup('EDVleitung',1)
con.addUser('Ernst Verse', 4)

con.addGroup('EDVpersonal',1)
con.addUser('Raimund Reim', 5)

con.addUser('Dirk Nagel', 5)
con.addUser('Erwin Schmitz', 5)

con.addGroup('Verwaltung',1)
con.addUser('Vera Stimmung', 6)

con.addGroup('Rechnungswesen',1)
con.addUser('Klara Sommer', 7)

con.addGroup('Personal',1)
con.addUser('Herrmann Winter', 8)

con.addGroup('Hausdienst',1)
con.addUser('Peter Fruehling', 9)

con.addGroup('Marketing',1)
con.addUser('Karmen Herbst', 10)

con.addGroup('Einkauf',1)
con.addUser('Werner Fassnacht', 11)

con.addGroup('Sekretariatsleitung',1)
con.addUser('Claudia Jahr', 12)

con.addGroup('Sekretariatspersonal',1)
con.addUser('Marlies Stunde', 13)




ldap = LDAP(con)
ldap.addUsersFromSQL()

