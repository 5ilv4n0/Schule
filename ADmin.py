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



global ldapHostName, domainName
ldapHostName = 'WIN-GMP1KUTS11M'
domainName = 'idealtec.org'



import sys, os, json, re
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
    global ldapHostName
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
			pathParts[0] = ldapHostName
		except IndexError:
			pass
		return (4*chr(92)) + (2*chr(92)).join(pathParts)
		
    def makeHomeDirectory(self, pathParts):
		try:
			pathParts[0] = ldapHostName
		except IndexError:
			pass
		return (4*chr(92)) + (2*chr(92)).join(pathParts)

    def __str__(self):
        return json.dumps(self.history, indent=4)


class LDAP(object):
	def __init__(self, mySQLConnection):
		self.mySQLConnection = mySQLConnection
		
	def addUser(self, firstName, lastName, securityGroup, mustChangePassword=True ,description='Ich bin ein Benutzer'):
		ouRoot = pyad.adcontainer.ADContainer.from_dn("DC=IDEALTEC,DC=ORG")
		
		try:
			ouRoot.create_container('Benutzer')
		except:
			pass
		ouUsers = pyad.adcontainer.ADContainer.from_dn("OU=Benutzer,DC=IDEALTEC,DC=ORG")
		user = pyad.aduser.ADUser.create('test', ouUsers, password='Changeme123', upn_suffix=None, enable=True, optional_attributes={})
			
		
		
	def addUsersFromSQL(self):
		ouRoot = pyad.adcontainer.ADContainer.from_dn("DC=IDEALTEC,DC=ORG")
		try:
			ouRoot.create_container('Benutzer')
		except:
			pass	
		finally:	
			ouUsers = pyad.adcontainer.ADContainer.from_dn("OU=Benutzer,DC=IDEALTEC,DC=ORG")
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
			os.popen(icaclsCommand).read()
			os.popen(icaclsMakeOwnerCommand).read()


con = MySQLConnection('localhost', 3306, 'root', '', 'CrashCom')
con.dropDatabase('CrashCom')
con.createDatabase('CrashCom')
con.useDatabase('CrashCom')

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






ouRoot = pyad.adcontainer.ADContainer.from_dn("DC=IDEALTEC,DC=ORG")
try:
	ouRoot.create_container('Gruppenstruktur')
except:
	pass
	
ous = con.getTable('OrganisationsEinheit')
for ouEntry in ous:
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
		ouGroup = pyad.adcontainer.ADContainer.from_dn("OU=" + ou + ",OU=Gruppenstruktur,DC=IDEALTEC,DC=ORG")
		try:
			pyad.adgroup.ADGroup.create(ou, ouGroup)
		except:
			pass

		
#ouUsers = pyad.adcontainer.ADContainer.from_dn("OU=Benutzer,DC=IDEALTEC,DC=ORG")



ldap = LDAP(con)
ldap.addUsersFromSQL()

