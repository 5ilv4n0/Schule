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

import sys, os, json, re
import win32com
from pyad import pyad
import MySQLdb as _mysql

global ADHostName, domainName, domain, ldapRoot

domainName = 'idealtec.org'
ADHostName = 'WIN-GMP1KUTS11M'
domain = domainName.upper().split('.')
databaseName = domain[0]
ldapRoot = 'DC=' + domain[0] + ',DC=' + domain[1]









def makeIntOrUseDefault(value, defaultValue=0):
    try:
        value = int(value)
        return value
    except ValueError:
        return defaultValue

class MySQLConnection(object):
    global ADHostName
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
            try:
                attributeLength = attribute[2]
            except IndexError:
                attributeLength = '0'
				
            attributeIsPrimaryKey = False
            attributeAutoIncrement = False
            if 'primaryKey' in attribute:
                attributeIsPrimaryKey = True
            if 'autoIncrement' in attribute:
                attributeAutoIncrement = True
            attributeCommandPart = attributeName + ' '
            if not attributeLength == '0':
                attributeCommandPart += attributeType + '(' + str(attributeLength) + ')'
            else:
                attributeCommandPart += attributeType
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
        
    def addUser(self, givenName, sn, displayName, description='', userPrincipalName='', samAccountName='', pwdLastSet=False, profilePath='', homeDrive='', homeDirectory='', *MemberOF):
        if pwdLastSet == True:
            pwdLastSet = '1'
        elif pwdLastSet == False:
            pwdLastSet = '0'
        profilePathParts = profilePath.split('\\')[1:]
        homeDirectoryParts = homeDirectory.split('\\')[1:]
        profilePath = self.makeProfilePath(profilePathParts)
        homeDirectory = self.makeHomeDirectory(homeDirectoryParts)
        newMemberOF = []
        for MemberOFID in MemberOF:
            newMemberOF.append(str(MemberOFID))
        newMemberOF = ','.join(newMemberOF)
        self.insertValues(tableName='Benutzer', givenName=givenName, sn=sn, displayName=displayName, description=description, userPrincipalName=userPrincipalName, samAccountName=samAccountName, pwdLastSet=pwdLastSet, profilePath=profilePath, homeDrive=homeDrive, homeDirectory=homeDirectory, MemberOF=newMemberOF)

    def makeProfilePath(self, pathParts):
		try:
			pathParts[0] = ADHostName
		except IndexError:
			pass
		return (4*chr(92)) + (2*chr(92)).join(pathParts)
		
    def makeHomeDirectory(self, pathParts):
		try:
			pathParts[0] = ADHostName
		except IndexError:
			pass
		return (4*chr(92)) + (2*chr(92)).join(pathParts)

    def __str__(self):
        return json.dumps(self.history, indent=4)


    def getUserOfGroup(self, groupName):
		users = []
		for user in self.executeSQLAndReturn("select * from Benutzer where MemberOF = '3' or MemberOF = '4'"):
			users.append(user[5])
		return users

class LDAP(object):
	def __init__(self, domainName, mySQLConnection):
		self.mySQLConnection = mySQLConnection
		self.domainName = domainName
		self.domain = domainName.upper().split('.')
		self.databaseName = self.domain[0]
		self.ldapRoot = 'DC=' + self.domain[0] + ',DC=' + self.domain[1]		
		self.ouRoot = pyad.adcontainer.ADContainer.from_dn(self.ldapRoot)

	def getUserGroupStructure(self):
		ouIDs = {}
		ous = self.mySQLConnection.getTable('OrganisationsEinheit')
		for ID, name, parent in ous:
			ouIDs[int(ID)] = name
			
		groupUsers = {}
		for UID, givenName, sn, displayName, description, userPrincipalName, samAccountName, pwdLastSet, profilePath ,homeDrive, homeDirectory, MemberOF in self.mySQLConnection.getTable('Benutzer'):
			for memberOfGroup in MemberOF.split(','):
				if not ouIDs[int(memberOfGroup)] in groupUsers.keys():
					groupUsers[ouIDs[int(memberOfGroup)]] = []
				groupUsers[ouIDs[int(memberOfGroup)]].append(userPrincipalName)
		return groupUsers


	def generateShareDirectories(self):
		groupUsers = self.getUserGroupStructure()
		for group in groupUsers.keys():
			try:
				os.makedirs('H:\\idealtec\\home\\Tausch\\'+group)
			except:
				pass
				
			userPrincipalNames = groupUsers[group]
			for userPrincipalName in userPrincipalNames:
				icaclsCommand = 'icacls ' + 'H:\\idealtec\\home\\Tausch\\' + group + ' /T /grant:r ' + userPrincipalName + ':(OI)(CI)F'
				os.popen(icaclsCommand).read()		


	def addUser(self, firstName, lastName, securityGroup, mustChangePassword=True ,description='Ich bin ein Benutzer'):
		try:
			self.ouRoot.create_container('Benutzer')
		except:
			pass
		ouUsers = pyad.adcontainer.ADContainer.from_dn('OU=Benutzer,' + self.ldapRoot)
		user = pyad.aduser.ADUser.create('test', ouUsers, password='Changeme123', upn_suffix=None, enable=True, optional_attributes={})

	def addUsersFromSQL(self):
		try:
			self.ouRoot.create_container('Benutzer')
		except:
			pass	
		finally:	
			ouUsers = pyad.adcontainer.ADContainer.from_dn('OU=Benutzer,' + self.ldapRoot)
	
		try:
			os.makedirs('H:\\idealtec\\home\\Global')
		except:
			pass
		
		for UID, givenName, sn, displayName, description, userPrincipalName, samAccountName, pwdLastSet, profilePath ,homeDrive, homeDirectory, MemberOF in self.mySQLConnection.getTable('Benutzer'):
				
			exAttr = {}
			exAttr['givenName'] = givenName
			exAttr['sn'] = sn			
			exAttr['initials'] = givenName[0] + sn[0]
			exAttr['displayName'] = displayName
			exAttr['samAccountName'] = samAccountName
			exAttr['description'] = description	
			exAttr['userPrincipalName'] = userPrincipalName + '@' + domainName
			if pwdLastSet == 1:
				exAttr['pwdLastSet'] = 0	
			exAttr['profilePath'] = profilePath
			exAttr['homeDrive'] = homeDrive
			exAttr['homeDirectory'] = homeDirectory
			try:
				os.makedirs('H:\\idealtec\\home\\' + samAccountName)
			except:
				pass
			reFilter = re.match(r'(.\d+-.\d+)',userPrincipalName)
			if reFilter == None:
				try:
					os.makedirs('H:\\idealtec\\profiles\\' + userPrincipalName)
				except:
					pass
				
			else:
				try:
					os.makedirs('H:\\idealtec\\profiles\\' + 'RX-PX')
				except:
					pass
			try:
				user = pyad.aduser.ADUser.create(userPrincipalName, ouUsers, password='Changeme1', upn_suffix=None, enable=True, optional_attributes=exAttr)
			except:
				pass
				
			icaclsCommand = 'icacls ' + 'H:\\idealtec\\home\\' + userPrincipalName + ' /T /grant:r ' + userPrincipalName + ':(OI)(CI)F'   
			icaclsMakeOwnerCommand = 'icacls ' + 'H:\\idealtec\\home\\' + userPrincipalName + ' /T /setowner ' + userPrincipalName
			icaclsGlobalCommand = 'icacls ' + 'H:\\idealtec\\home\\Global /T /grant:r ' + userPrincipalName + ':(OI)(CI)RX'
			os.popen(icaclsCommand).read()
			os.popen(icaclsMakeOwnerCommand).read()
			os.popen(icaclsGlobalCommand).read()
			
			
			
		schulungsLeiter =  self.mySQLConnection.getUserOfGroup('')
		
		for room in xrange(0,2):
			room += 1 	
			
			try:
				os.makedirs('H:\\idealtec\\home\\' + 'Schulungsraum'+str(room))
			except:
				pass
				
			try:
				os.makedirs('H:\\idealtec\\home\\' + 'Schulungen')
			except:
				pass
			
			for user in self.getUserNamesOfRoom(room):
				print '########->>>>>',user
				for userL in schulungsLeiter:
					icaclsHomesCommand = 'icacls ' + 'H:\\idealtec\\home\\' + user + ' /T /grant:r ' + userL + ':(OI)(CI)F' 
					os.popen(icaclsHomesCommand)
				icaclsCommand = 'icacls ' + 'H:\\idealtec\\home\\' + 'Schulungsraum'+str(room) + ' /T /grant:r ' + user + ':(OI)(CI)RX' 	
				os.popen(icaclsCommand).read()
							

			for user in schulungsLeiter:
				icaclsFolderCommand = 'icacls ' + 'H:\\idealtec\\home\\' + 'Schulungen /T /grant:r ' + user + ':(OI)(CI)F'
				icaclsCommand = 'icacls ' + 'H:\\idealtec\\home\\' + 'Schulungsraum'+str(room) + ' /T /grant:r ' + user + ':(OI)(CI)F' 	
				os.popen(icaclsFolderCommand).read()
				os.popen(icaclsCommand).read()
				
				
				####################################				
		
		 
			                             	
	def createOU(self, LDAPObject, name):
		try:
			LDAPObject.create_container(name)
			return True
		except:
			return False
			
	def createOUAndGroup(self, LDAPObject, name):
		self.createOU(LDAPObject, name)
		try:
			ouGroup = pyad.adcontainer.ADContainer.from_dn("OU=" + name + ',OU=Gruppenstruktur,DC=IDEALTEC,DC=ORG')
		except:
			return False
		group = False
		try:
			group = pyad.adgroup.ADGroup.create(name, ouGroup)
		except:
			pass

		userGroupStructure = self.getUserGroupStructure()
		#group = pyad.adcontainer.ADContainer.from_dn('OU=' + name + ',OU=Gruppenstruktur,' + self.ldapRoot)
		usersOfGroup = userGroupStructure[name]
		userObjects = []
		for user in usersOfGroup:
			user = pyad.adobject.ADObject.from_dn('CN=' + user + ',OU=Benutzer,' + self.ldapRoot)
			userObjects.append(user)
		if not group == False:
			group.add_members(userObjects)
			
	def createGroupStructure(self):
		self.createOU(self.ouRoot, 'Gruppenstruktur')
		ouGroupStructure = pyad.adcontainer.ADContainer.from_dn('OU=Gruppenstruktur,' + self.ldapRoot)
		ous = self.mySQLConnection.getTable('OrganisationsEinheit')
		for ouEntry in ous:
			ID, ou, parent = ouEntry
			if parent == '':
				self.createOU(self.ouRoot, ou)
			else:
				self.createOUAndGroup(ouGroupStructure, ou)		


	def getUserNamesOfRoom(self, roomNumber):
		users = []
		for UID, givenName, sn, displayName, description, userPrincipalName, samAccountName, pwdLastSet, profilePath ,homeDrive, homeDirectory, MemberOF in self.mySQLConnection.getTable('Benutzer'):
			if userPrincipalName[1] == str(roomNumber):
				users.append(userPrincipalName)
		return users





con =  MySQLConnection('localhost', 3306, 'root', '', domainName)
print con
if 'renewdb' in sys.argv:
	print 'renew the database...',
	con.dropDatabase(databaseName)
	con.createDatabase(databaseName)
	con.useDatabase(databaseName)
	con.createTable(name='OrganisationsEinheit', attributes=['OUID int 11 primaryKey autoIncrement', 'Name varchar 255', 'parent varchar 255'])
	con.createTable(name='Benutzer', attributes=['UID int 11 primaryKey autoIncrement', 'givenName varchar 255','sn varchar 255','displayName varchar 255','description varchar 255','userPrincipalName varchar 255','samAccountName varchar 255','pwdLastSet bool','profilePath varchar 255','homeDrive varchar 255','homeDirectory varchar 255','MemberOF varchar 255'])
	con.addOU('Gruppenstruktur')
	con.addOU('Geschaeftsfuehrung','Gruppenstruktur')
	con.addOU('Schulungsleitung','Gruppenstruktur')
	con.addOU('Schulungspersonal','Gruppenstruktur')
	con.addOU('Schulungsteilnehmer','Gruppenstruktur')
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
	con.addUser('Dietmar','Renzen','Renzen, Dietmar','Geschaeftsfuehrer','dietmar.renzen','dietmar.renzen',True,'\\idealtec\profiles\dietmar.renzen','H:','\\idealtec\home\dietmar.renzen',2)
	con.addUser('Peter','Klug','Klug, Peter','Schulungsleiter','peter.klug','peter.klug',True,'\\idealtec\profiles\peter.klug','H:','\\idealtec\home\peter.klug',3)
	con.addUser('Dieter','Gross','Gross, Dieter','PC-Technik','dieter.gross','dieter.gross',True,'\\idealtec\profiles\dieter.gross','H:','\\idealtec\home\dieter.gross',4)
	con.addUser('Evelyn','Schmal','Schmal, Evelyn','Office-Anwendung','evelyn.schmal','evelyn.schmal',True,'\\idealtec\profiles\evelyn.schmal','H:','\\idealtec\home\evelyn.schmal',4)
	con.addUser('Ottfried','Kall','Kall, Ottfried','Grafik','ottfried.kall','ottfried.kall',True,'\\idealtec\profiles\ottfried.kall','H:','\\idealtec\home\ottfried.kall',4)
	con.addUser('Tom','Schmaechtle','Schmaechtle,Tom','Programmierung','top.schmaechtle','tom.schmaechtel',True,'\\idealtec\profiles\tom.schmaechtel','H:','\\idealtec\home\tom.schmaechtel',4)
	con.addUser('Paul','Starke','Starke, Paul','Fuehrungstraining','paul.starke','paul.starke',True,'\\idealtec\profiles\paul.starke','H:','\\idealtec\home\paul.starke',4)
	con.addUser('Ernst','Verse','Verse, Ernst','EDV','ernst.verse','ernst.verse',True,'\\idealtec\profiles\ernst.verse','H:','\\idealtec\home\ernst.verse',6)
	con.addUser('Raimund','Reim','Reim, Raimund','EDV-Personal','raimund.reim','raimund.reim',True,'\\idealtec\profiles\raimund.reim','H:','\\idealtec\home\raimund.reim',7)
	con.addUser('Dirk','Nagel','Nagel, Dirk','EDV-Personal','dirk.nagel','dirk.nagel',True,'\\idealtec\profiles\dirk.nagel','H:','\\idealtec\home\dirk.nagel',7)
	con.addUser('Erwin','Schmitz','Schmitz, Erwin','EDV-Personal','erwin.schmitz','erwin.schmitz',True,'\\idealtec\profiles\erwin.schmitz','H:','\\idealtec\home\erwin.schmitz',7)
	con.addUser('Vera','Stimmung','Stimmung, Vera','Verwaltungsleitung','vera.stimmung','vera.stimmung',True,'\\idealtec\profiles\vera.stimmung','H:','\\idealtec\home\vera.stimmung',8)
	con.addUser('Clara','Sommer','Sommer, Clara','Rechnungswesen','clara.sommer','clara.sommer',True,'\\idealtec\profiles\clara.sommer','H:','\\idealtec\home\clara.sommer',9)
	con.addUser('Hermann','Winter','Winter, Hermann','Personal','hermann.winter','herman.winter',True,'\\idealtec\profiles\herman.winter','H:','\\idealtec\home\herman.winter',10)
	con.addUser('Peter','Fruehling','Fruehling, Peter','Hausdienste','peter.fruehling','peter.fruehling',True,'\\idealtec\profiles\peter.fruehling','H:','\\idealtec\home\peter.fruehling',12)
	con.addUser('Carmen','Herbst','Herbst, Carmen','Marketing','carmen.herbst','carmen.herbst',True,'\\idealtec\profiles\carmen.herbst','H:','\\idealtec\home\carmen.herbst',13)
	con.addUser('Werner','Fassnacht','Fassnacht, Werner','Einkauf','werner.fassnacht','werner.fassnacht',True,'\\idealtec\profiles\werner.fassnacht','H:','\\idealtec\home\werner.fassnacht',11)
	con.addUser('Claudia','Jahr','Jahr, Claudia','Sekretariatsleitung','claudia.jahr','claudia.jahr',True,'\\idealtec\profiles\claudia.jahr','H:','\\idealtec\home\claudia.jahr',14)
	con.addUser('Marlies','Stunde','Stunde, Marlies','Sekretariatspersonal','marlies.stunde','marlies.stunde',True,'\\idealtec\profiles\marlies.stunde','H:','\\idealtec\home\marlies.stunde',15)
	con.addUser('R1-P1','R1-P1','R1-P1','Schulungsraum 1 Platz 1','R1-P1','R1-P1',True,'','','',5)
	con.addUser('R1-P2','R1-P2','R1-P2','Schulungsraum 1 Platz 2','R1-P2','R1-P2',True,'','','',5)
	con.addUser('R1-P3','R1-P3','R1-P3','Schulungsraum 1 Platz 3','R1-P3','R1-P3',True,'','','',5)
	con.addUser('R1-P4','R1-P4','R1-P4','Schulungsraum 1 Platz 4','R1-P4','R1-P4',True,'','','',5)
	con.addUser('R1-P5','R1-P5','R1-P5','Schulungsraum 1 Platz 5','R1-P5','R1-P5',True,'','','',5)
	con.addUser('R1-P6','R1-P6','R1-P6','Schulungsraum 1 Platz 6','R1-P6','R1-P6',True,'','','',5)
	con.addUser('R1-P7','R1-P7','R1-P7','Schulungsraum 1 Platz 7','R1-P7','R1-P7',True,'','','',5)
	con.addUser('R1-P8','R1-P8','R1-P8','Schulungsraum 1 Platz 8','R1-P8','R1-P8',True,'','','',5)
	con.addUser('R1-P9','R1-P9','R1-P9','Schulungsraum 1 Platz 9','R1-P9','R1-P9',True,'','','',5)
	con.addUser('R1-P10','R1-P10','R1-P10','Schulungsraum 1 Platz 10','R1-P10','R1-P10',True,'','','',5)
	con.addUser('R1-P11','R1-P11','R1-P11','Schulungsraum 1 Platz 11','R1-P11','R1-P11',True,'','','',5)
	con.addUser('R1-P12','R1-P12','R1-P12','Schulungsraum 1 Platz 12','R1-P12','R1-P12',True,'','','',5)
	con.addUser('R2-P1','R2-P1','R2-P1','Schulungsraum 2 Platz 1','R2-P1','R2-P1',True,'','','',5)
	con.addUser('R2-P2','R2-P2','R2-P2','Schulungsraum 2 Platz 2','R2-P2','R2-P2',True,'','','',5)
	con.addUser('R2-P3','R2-P3','R2-P3','Schulungsraum 2 Platz 3','R2-P3','R2-P3',True,'','','',5)
	con.addUser('R2-P4','R2-P4','R2-P4','Schulungsraum 2 Platz 4','R2-P4','R2-P4',True,'','','',5)
	con.addUser('R2-P5','R2-P5','R2-P5','Schulungsraum 2 Platz 5','R2-P5','R2-P5',True,'','','',5)
	con.addUser('R2-P6','R2-P6','R2-P6','Schulungsraum 2 Platz 6','R2-P6','R2-P6',True,'','','',5)
	con.addUser('R2-P7','R2-P7','R2-P7','Schulungsraum 2 Platz 7','R2-P7','R2-P7',True,'','','',5)
	con.addUser('R2-P8','R2-P8','R2-P8','Schulungsraum 2 Platz 8','R2-P8','R2-P8',True,'','','',5)
	con.addUser('R2-P9','R2-P9','R2-P9','Schulungsraum 2 Platz 9','R2-P9','R2-P9',True,'','','',5)
	con.addUser('R2-P10','R2-P10','R2-P10','Schulungsraum 2 Platz 10','R2-P10','R2-P10',True,'','','',5)
	con.addUser('R2-P11','R2-P11','R2-P11','Schulungsraum 2 Platz 11','R2-P11','R2-P11',True,'','','',5)
	con.addUser('R2-P12','R2-P12','R2-P12','Schulungsraum 2 Platz 12','R2-P12','R2-P12',True,'','','',5)
	print '[OK]'
else:
	con.useDatabase(databaseName)

print con.getUserOfGroup('')
		
#ouUsers = pyad.adcontainer.ADContainer.from_dn("OU=Benutzer,DC=IDEALTEC,DC=ORG")

#~ 
#~ 
ldap = LDAP(domainName, con)
ldap.createGroupStructure()
ldap.addUsersFromSQL()
ldap.generateShareDirectories()


