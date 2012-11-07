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
 
    def addOU(self, ouName, parent=''):
        self.insertValues(tableName='OrganisationsEinheit', Name=ouName, parent=parent)

    def addGroup(self, groupName, OUID): 
        self.insertValues(tableName='SicherheitsGruppe', Name=groupName, OrganisationsEinheit_OUID=OUID)
        return True
        
    def addUser(self, givenName, sn, displayName, description='', userPrincipalName='', samAccountName='', pwdLastSet='bbbbbb', profilePath='', homeDrive='', homeDirectory='', *MemberOF):
        newMemberOF = []
        for MemberOFID in MemberOF:
            newMemberOF.append(str(MemberOFID))
        newMemberOF = ','.join(newMemberOF)
        self.insertValues(tableName='Benutzer', givenName=givenName, sn=sn, displayName=displayName, description=description, userPrincipalName=userPrincipalName, samAccountName=samAccountName, pwdLastSet=pwdLastSet, profilePath=profilePath, homeDrive=homeDrive, homeDirectory=homeDirectory, MemberOF=newMemberOF)

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
		ouUsers = pyad.adcontainer.ADContainer.from_dn("OU=Benutzer,DC=IDEALTEC,DC=ORG")
		for UID, givenName, sn, displayName, description, userPrincipalName, samAccountName, pwdLastSet, profilePath ,homeDrive, homeDirectory, MemberOF in self.mySQLConnection.getTable('Benutzer'):
			print givenName, sn, displayName, description, userPrincipalName, samAccountName, pwdLastSet, profilePath ,homeDrive, homeDirectory, MemberOF
			principalName = userPrincipalName		
			exAttr = {}
			exAttr['givenName'] = givenName
			exAttr['sn'] = sn			
			exAttr['initials'] = givenName[0] + sn[0]
			exAttr['displayName'] = displayName
			exAttr['samAccountName'] = samAccountName
			#exAttr['nTSecurityDescriptor'] = True
			exAttr['description'] = description		

			user = pyad.aduser.ADUser.create(principalName, ouUsers, password='Changeme123', upn_suffix=None, enable=True, optional_attributes=exAttr)

		

con = MySQLConnection('localhost', 3306, 'root', '', 'CrashCom')
con.dropDatabase('CrashCom')
con.createDatabase('CrashCom')
con.useDatabase('CrashCom')

con.createTable(name='OrganisationsEinheit', attributes=['OUID int 11 primaryKey autoIncrement', 'Name varchar 255', 'parent varchar 255'])
con.createTable(name='Benutzer', attributes=['UID int 11 primaryKey autoIncrement', 'givenName varchar 255','sn varchar 255','displayName varchar 255','description varchar 255','userPrincipalName varchar 255','samAccountName varchar 255','pwdLastSet varchar 255','profilePath varchar 255','homeDrive varchar 255','homeDirectory varchar 255','MemberOF varchar 255'])

con.addOU('Gruppenstruktur')
con.addOU('Geschaeftsfuehrung','Gruppenstruktur')
con.addOU('Schulungsleitung','Gruppenstruktur')
con.addOU('Schulungspersonal','Gruppenstruktur')
con.addOU('EDVleitung','Gruppenstruktur')
con.addOU('EDVpersonal','Gruppenstruktur')
con.addOU('Verwaltung','Gruppenstruktur')
con.addOU('Rechnungswesen','Gruppenstruktur')
con.addOU('Personal','Gruppenstruktur')
con.addOU('Einkauf','Gruppenstruktur')
con.addOU('Hausdienst','Gruppenstruktur')
con.addOU('Marketing','Gruppenstruktur')
con.addOU('Sekretariatsleitung','Gruppenstruktur')
con.addOU('Sekretariatspersonal','Gruppenstruktur')

con.addUser('Dietmar', 'Renzen', 'Dietmar Renzen')
con.addUser('Peter', 'Klug', 'Peter Klug')
con.addUser('Dieter', 'Gross', 'Dieter Gross')
con.addUser('Evelin', 'Schmal', 'Evelin Schmal')
con.addUser('Ottfried', 'Kall', 'Ottfried Kall')
con.addUser('Schmaechtle', 'Tom', 'Schmaechtle Tom')
con.addUser('Starke', 'Paul', 'Starke Paul')
con.addUser('Verse', 'Ernst', 'Verse Ernst')
con.addUser('Raimund','Reim','Raimund Reim')
con.addUser('Dirk','Nagel','Dirk Nagel')
con.addUser('Erwin','Schmitz','Erwin Schmitz')
con.addUser('Vera','Stimmung','Vera Stimmung')
con.addUser('Klara','Sommer','Klara Sommer')
con.addUser('Herrmann','Winter','Herrmann Winter')
con.addUser('Peter','Fruehling','Peter Fruehling')
con.addUser('Karmen','Herbst','Karmen Herbst')
con.addUser('Werner','Fassnacht','Werner Fassnacht')
con.addUser('Claudia','Jahr','Claudia Jahr')
con.addUser('Marlies','Stunde','Marlies Stunde')


print len(con.getTable('Benutzer')[0])


ouRoot = pyad.adcontainer.ADContainer.from_dn("DC=IDEALTEC,DC=ORG")
try:
	ouRoot.create_container('Gruppenstruktur')
except:
	pass
	
ous = con.getTable('OrganisationsEinheit')
for ouEntry in ous:
	print ouEntry
	ou = ouEntry[1]
	parent = ouEntry[2]
	if parent == '':
		try:
			ouRoot.create_container(ou)
		except:
			pass
	else:
		ouGroupStructure = pyad.adcontainer.ADContainer.from_dn("OU=Gruppenstruktur,DC=IDEALTEC,DC=ORG")
		try:
			ouGroupStructure.create_container(ou)
		except:
			pass


		
ouUsers = pyad.adcontainer.ADContainer.from_dn("OU=Benutzer,DC=IDEALTEC,DC=ORG")
#print ouUsers


ldap = LDAP(con)
ldap.addUsersFromSQL()

