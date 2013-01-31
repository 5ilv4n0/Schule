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
import json
import re
import os ,sys
from pyad import pyad
import UserGroup



def joinToString(strings, seperator=' '):
    return seperator.join(strings)

def loadJsonFile(filePath):
    try:
        with open(filePath) as f:
            content = json.load(f)
        return content
    except IOError:
        return {}
    
def tryToMakeInteger(value):
    try:
        return int(value)
    except:
        return value
    



class LDAPAdministration(object):
    samAccountNames = []
    def __init__(self, configFilePath):
        self.configFilePath         = configFilePath
        self.config                 = loadJsonFile(configFilePath)
        self.config                 = self.readConfigOrGetInput()
        self.userAndGroupFilePath   = self.config['userAndGroupFilePath']
        if not os.path.isfile(self.userAndGroupFilePath):
            UserGroup.clearJsonFile(self.userAndGroupFilePath)
        self.usersAndGroups         = loadJsonFile(self.userAndGroupFilePath)
        self.ldapRootPath           = self.getLDAPRootPath(self.config)
        self.ldapRootObject         = self.callOrganisationUnit(self.ldapRootPath)
        self.company                = self.config['domainName'].split('.')[0]
        self.homeAndProfileRootPath = ''.join((self.config['homeAndProfileDriveLetter'], ':', chr(92), self.company))
        self.localProfilesPath      = os.path.join(self.homeAndProfileRootPath, 'profiles')
        self.localHomesPath         = os.path.join(self.homeAndProfileRootPath, 'homes') 
        self.userObjects            = {}
        self.groupObjects           = {}
        self.ldapPathOfGroupStructureOUObject       = self.createOrganisationUnitInRootIfNotExists('Gruppenstruktur')
        self.ldapPathOfUsersOUObject                = self.createOrganisationUnitInRootIfNotExists('Benutzer')
        self.groupStructureOUObject                 = self.callOrganisationUnit(self.ldapPathOfGroupStructureOUObject)
        self.usersOUObject                          = self.callOrganisationUnit(self.ldapPathOfUsersOUObject)
        self.createGroupsFromDatabase()

        
        
    def readConfigOrGetInput(self):
        newConfig = {}
        keysMustExists = ('userAndGroupFilePath', 
                          'serverHostName',
                          'domainName',
                          'defaultPassword',
                          'homeAndProfileDriveLetter',
                          'usersHomeDriveLetter',
                          'numberOfClassRooms',
                          'numberOfComputerPerClassRoom',
                          'groupOfClassRoomUsers'
                          )
        for key in keysMustExists:
            configMustWrittenNew = False
            try:
                a = self.config[key]
                newConfig[key] = a
            except KeyError:
                configMustWrittenNew = True
                newConfig[key] = tryToMakeInteger(raw_input(key+': '))
        if configMustWrittenNew:        
            with open(self.configFilePath, 'w') as f:
                f.write(json.dumps(newConfig, indent=4))

        return newConfig

    def getLDAPRootPath(self, config):
        self.domain     = config['domainName'].upper().split('.')
        stringParts     = ('DC=', self.domain[0], ',DC=', self.domain[1]) 
        ldapRootPath    = joinToString(stringParts, '')
        return ldapRootPath

    def readSamAccountNames(self):
        samAccNames = []
        for userName in self.usersAndGroups['users'].keys():
            nameData = self.getADNames(userName)
            samAccNames.append(self.makeSamAccountName(nameData['firstName'], nameData['lastName']))
        return samAccNames

    def getADNames(self, userName):
        names               = userName.split()
        returnData          = {}
        if not len(names) == 1:
            firstName           = names[0]
            lastName            = names[-1]
            displayName         = self.makeDisplayName(firstName, lastName)
            principalName       = self.makeUserPrincipalName(firstName, lastName)
            samAccountName      = self.makeSamAccountName(firstName, lastName)
            returnData['firstName']         = firstName
            returnData['lastName']          = lastName 
            returnData['principalName']     = principalName 
            returnData['displayName']       = displayName           
            returnData['samAccountName']    = samAccountName
        else:
            firstName           = names[0][0]
            lastName            = names[0][1:]
            displayName         = userName
            principalName       = userName
            samAccountName      = self.makeSamAccountName(firstName, lastName)
            returnData['firstName']         = firstName
            returnData['lastName']          = lastName 
            returnData['principalName']     = principalName 
            returnData['displayName']       = displayName           
            returnData['samAccountName']    = samAccountName            
        return returnData

    def makeDisplayName(self, firstName, lastName):
        return ', '.join((lastName, firstName))

    def makeUserPrincipalName(self, firstName, lastName):
        firstName   = firstName.lower()
        lastName    = lastName.lower()
        return '.'.join((firstName, lastName))

    def makeSamAccountName(self, firstName, lastName):
        tmpSamAccName = ''.join((firstName[0],lastName))
        count = 0
        while tmpSamAccName in self.samAccountNames:
            count += 1
            tmpSamAccName = ''.join((firstName[:count],lastName))
            if tmpSamAccName == ''.join((firstName[:(count+1)],lastName)):
                tmpSamAccName = ''.join((firstName,lastName,'_'+str(count)))
            if len(tmpSamAccName) > 20:
                tmpSamAccName = ''.join((firstName,str(count),lastName,))
        return tmpSamAccName


    def generateStructure(self):
        self.createDirectoryStructure()

        self.ldapPathOfGroupStructureOUObject       = self.createOrganisationUnitInRootIfNotExists('Gruppenstruktur')
        self.ldapPathOfUsersOUObject                = self.createOrganisationUnitInRootIfNotExists('Benutzer')
        self.groupStructureOUObject                 = self.callOrganisationUnit(self.ldapPathOfGroupStructureOUObject)
        self.usersOUObject                          = self.callOrganisationUnit(self.ldapPathOfUsersOUObject)
        
        self.deleteAllUsers()       

        self.deleteGroupStructure()
        self.createGroupsFromDatabase()
        self.createUsersFromDatabase()
        
    def createDirectoryStructure(self):
        classRoomLength = len(str(self.config['numberOfClassRooms']))
        self.createAndShareDirectory(self.homeAndProfileRootPath, False)
        self.createDirectory(self.localProfilesPath)
        self.createDirectory(self.localHomesPath)
        self.createDirectory(os.path.join(self.localHomesPath, 'global'))
        self.createDirectory(os.path.join(self.localHomesPath, 'schulungen'))
        for classRoomID in xrange(0, self.config['numberOfClassRooms']):
            directoryPath = os.path.join(self.localHomesPath, 'schulungsraum'+str(classRoomID).rjust(classRoomLength,'0'))
            self.createDirectory(directoryPath)

    def createOrganisationUnitInRootIfNotExists(self, ouName):
        ldapPath = ''.join(('OU=', ouName, ',', self.ldapRootPath))
        if not self.existsOrganisationUnit(ldapPath):
            self.createOrganisationUnit(self.ldapRootObject, ouName)
        return ldapPath

    def createOrganisationUnit(self, ldapObject, ouName):
        try:
            ouObject = ldapObject.create_container(ouName)
            return True
        except:
            return False

    def existsOrganisationUnit(self, ldapOUPath):
        try:
            ldapOU = self.callOrganisationUnit(ldapOUPath)
            return True
        except:
            return False

    def callOrganisationUnit(self, ldapPath):
        return pyad.adcontainer.ADContainer.from_dn(ldapPath)

    def createGroupsFromDatabase(self):
        for groupName in self.usersAndGroups['groups']:
            try:
                self.createOrganisationUnit(self.groupStructureOUObject, groupName)
	            groupOUPath = ''.join(('OU=',groupName,',',self.ldapPathOfGroupStructureOUObject))
	            groupOU = self.callOrganisationUnit(groupOUPath)
	            self.createGroup(groupOU, groupName)
            except:
	            pass
				
				
    def deleteGroupStructure(self):
        try:
            for ou in self.callOrganisationUnit(self.ldapPathOfGroupStructureOUObject).get_children():
                for group in ou.get_children():
                    group.delete()
                ou.delete()        
        except:
            pass


    def deleteAllUsers(self):
        try:
            for user in self.usersOUObject.get_children():
                user.delete()
        except:
            pass
  

    def resetUser(self, principalName):
        self.resetUserPassword(principalName)
        self.deleteHomeDirectory(principalName)
        self.createHomeDirectory(principalName)

    def resetUserPassword(self, principalName):
        os.system('net user '+principalName+' '+self.config['defaultPassword'])
        

    def deleteUser(self, principalName):
        try:
            for user in self.usersOUObject.get_children():
                if user.dn.split(',')[0].replace('CN=','') == principalName:
                    user.delete()
        except:
            pass     

    def createGroup(self, groupObject, groupName):
        try:
	        ldapGroupPath = ''.join(('CN=', groupName, ',', 'OU=', groupName, ',', self.ldapPathOfGroupStructureOUObject))
	        if not self.existsGroup(ldapGroupPath):
	            self.groupObjects[groupName] = pyad.adgroup.ADGroup.create(groupName, groupObject)
	        else:
	            self.groupObjects[groupName] = self.callGroup(ldapGroupPath)
        except:
            pass

    def existsGroup(self, ldapGroupPath):
        try:
            groupObject = self.callGroup(ldapGroupPath)
            return True
        except:
            return False

    def callGroup(self, ldapPath):
        return pyad.adobject.ADObject(ldapPath)


    def createUsersFromDatabase(self):
        for userName in sorted(self.usersAndGroups['users']):
            try:
	            adNamesInfo     = self.getADNames(userName)
	            principalName   = adNamesInfo['principalName']
	            description     = self.usersAndGroups['users'][userName]['description']
	            groups          = self.usersAndGroups['users'][userName]['groups']
	            self.createUser(self.usersOUObject, userName, self.config['defaultPassword'], True, True, description)
	            for groupName in groups:
	                self.addUserToGroup(principalName, groupName)
            except:
                pass
                
        self.createClassRoomUsers()
                
    def createClassRoomUsers(self):
        classRoomLength = len(str(self.config['numberOfClassRooms']))
        userLength = len(str(self.config['numberOfComputerPerClassRoom'])) 
        for classRoomID in xrange(0, self.config['numberOfClassRooms']):
            for userID in xrange(0, self.config['numberOfComputerPerClassRoom']):
                userName        = ''.join(('S', str(classRoomID).rjust(classRoomLength,'0'), '-', str(userID).rjust(userLength,'0')))
                groupName       = self.config['groupOfClassRoomUsers']
                adNamesInfo     = self.getADNames(userName)
                principalName   = adNamesInfo['principalName']
                description     = groupName + ' ' + adNamesInfo['principalName']
                self.createUser(self.usersOUObject, userName, self.config['defaultPassword'], True, True, description)
                self.addUserToGroup(principalName, groupName)
                directoryPath = os.path.join(self.localHomesPath, 'schulungsraum'+str(classRoomID).rjust(classRoomLength,'0'))
                self.setAccessRulesOfDirectoryForUser(principalName, directoryPath, 'RX')
        leaderUsers = self.getLeaderUsers()
        for user in leaderUsers:
            principalName = re.findall(r'CN=(.+),OU.+', user.__dict__['_ADObject__ads_path'])[0]
            path = os.path.join(self.localHomesPath, 'schulungen')
            self.setAccessRulesOfDirectoryForUser(principalName, path)
            
    def resetClassRoom(self, classRoomID):
        classRoomLength = len(str(self.config['numberOfClassRooms']))
        userLength = len(str(self.config['numberOfComputerPerClassRoom'])) 
        for userID in xrange(0, self.config['numberOfComputerPerClassRoom']):
            userName        = ''.join(('S', str(classRoomID).rjust(classRoomLength,'0'), '-', str(userID).rjust(userLength,'0')))
            adNamesInfo     = self.getADNames(userName)
            principalName   = adNamesInfo['principalName']
            self.resetUser(principalName)
            
    def getLeaderUsers(self):
        try:        
            leaderUsers = self.groupObjects['Schulungsleitung'].get_members()
            leaderUsers.extend(self.groupObjects['Schulungspersonal'].get_members())
        except KeyError:
            leaderUsers = []
        try:        
            leaderUsers.extend(self.groupObjects['Schulungspersonal'].get_members())
        except KeyError:            
            pass
            
        return leaderUsers

    def addUserToGroup(self, principalName, groupName):
        try:
            self.groupObjects[groupName].add_members(self.userObjects[principalName])
        except KeyError:
            print 'Gruppe "' + groupName + '" existiert nicht.\nMuss vorher mit "UserGroup.py addgroup" angelegt werden.\nAbbruch.'
            sys.exit(1)
        return True

    def createUser(self, OUObject, userName, password=None, changePasswordByLogin=False, accountIsEnabled=True, description=''):
        try:
	        adNamesInfo         = self.getADNames(userName)
	        firstName           = adNamesInfo['firstName']
	        lastName            = adNamesInfo['lastName']
	        principalName       = adNamesInfo['principalName']
	        displayName         = adNamesInfo['displayName']         
	        samAccountName      = adNamesInfo['samAccountName']
	        userAttributes                      = {}        
	        userAttributes['givenName']         = firstName
	        userAttributes['sn']                = lastName			
	        userAttributes['initials']          = self.getInitials(firstName, lastName)
	        userAttributes['displayName']       = displayName
	        userAttributes['samAccountName']    = principalName
	        userAttributes['description']       = description	
	        userAttributes['userPrincipalName'] = ''.join((principalName, '@', self.config['domainName']))
	        userAttributes['homeDrive']         = self.config['usersHomeDriveLetter'] + ':'
	        userAttributes['profilePath']       = self.getProfilePath(principalName)
	        userAttributes['homeDirectory']     = self.getHomePath(principalName)       
	        if changePasswordByLogin:
	            userAttributes['pwdLastSet'] = 0
	        if not self.existsUser(principalName):
	            self.userObjects[principalName] = pyad.aduser.ADUser.create(principalName, OUObject, password=password, upn_suffix=None, enable=accountIsEnabled, optional_attributes=userAttributes)
	        else:
	            self.userObjects[principalName] = self.callUser(principalName)
	        self.createHomeDirectory(principalName)
	        print principalName
        except:
            pass

    def existsUser(self, principalName):
        try:
            userLdapPath = pyad.adsearch.by_cn(principalName)
            return True
        except:
            return False

    def callUser(self, principalName):
        if not self.existsUser(principalName):
            return False
        userLdapPath = self.getUserLdapPath(principalName)
        return pyad.adobject.ADObject(userLdapPath)

    def getInitials(self, firstName, lastName):
        if len(firstName) == 1:
            tmpName = firstName + lastName
            tmpName = tmpName.replace('-','')
            return tmpName
        return firstName[0]+lastName[0]


    def createHomeDirectory(self, principalName):
        netPath = self.getHomePath(principalName)
        homePath = os.path.join(self.localHomesPath, principalName)
        self.createDirectory(homePath)
        self.setAccessRulesOfHomeDirectory(homePath)
        return True
        
    def deleteHomeDirectory(self, principalName):
        homePath = os.path.join(self.localHomesPath, principalName)
        self.deleteDirectory(homePath)
        return True 

    def setAccessRulesOfHomeDirectory(self, homePath):
        principalName = os.path.split(homePath)[1]
        icaclsAccessCommand = 'icacls ' + homePath + ' /T /grant:r ' + principalName + ':(OI)(CI)F'   
        icaclsMakeOwnerCommand = 'icacls ' + homePath + ' /T /setowner ' + principalName
        icaclsGlobalCommand = 'icacls ' + os.path.join(self.localHomesPath, 'global') + ' /T /grant:r ' + principalName + ':(OI)(CI)RX'
        os.popen(icaclsMakeOwnerCommand + ' >> .out 2>&1')        
        os.popen(icaclsAccessCommand + ' >> .out 2>&1')
        os.popen(icaclsGlobalCommand + ' >> .out 2>&1')
        
    def setAccessRulesOfDirectoryForUser(self, principalName, path, rule='F'):
        icaclsAccessCommand = 'icacls ' + path + ' /T /grant:r ' + principalName + ':(OI)(CI)'+rule
        os.popen(icaclsAccessCommand + ' >> .out 2>&1')

    def createAndShareDirectory(self, path, visible=True):
        if self.createDirectory(path) and self.shareDirectory(path, visible):
            return True        

    def createDirectory(self, path):
        if not os.path.exists(path):
            os.makedirs(path)
        return True   

    def deleteDirectory(self, d):
        if os.path.exists(d):
	        for path in (os.path.join(d,f) for f in os.listdir(d)):
	            if os.path.isdir(path):
	                self.deleteDirectory(path)
	            else:
	                os.unlink(path)
	        os.rmdir(d)
	        return True  

    def shareDirectory(self, path, visible=True):
        self.shareName = self.company
        if not visible:
            self.shareName += '$'
        os.popen(''.join(('net share ', self.shareName, '=', path)))
        return True


    def getProfilePath(self, principalName):
        if len(principalName.split()) == 1:
            return self.getNetPath() + chr(92) + 'profiles' + chr(92) + 'SXX-XX'
        return self.getNetPath() + chr(92) + 'profiles' + chr(92) + principalName 

    def getHomePath(self, principalName):
        return self.getNetPath() + chr(92) + 'homes' + chr(92) + principalName 

    def getNetPath(self):
        self.shareName = self.company
        #domain = self.config['domainName'].split('.')[0]
        return (2*chr(92)) + self.config['serverHostName'] + chr(92) + self.shareName

    def getUserLdapPath(self, principalName):
        if self.existsUser(principalName):
            return pyad.adsearch.by_cn(principalName)


    def __str__(self):
        return json.dumps(self.__dict__, indent=4)




if len(sys.argv) < 2:
	print 'SYNTAX:'
	print sys.argv[0], '<command> [parameters]'
	print ''
	print 'COMMANDS:'
	print '   --init-ad'
	print '   --reset-user <userName>'
	print '   --reset-room <roomNumber>'
	print '   --reset-user-pw <userName>'
	sys.exit(0)


configFilePath          = 'manageAD.conf'
ldap = LDAPAdministration(configFilePath)


if sys.argv[1] == '--init-ad':
	ldap.generateStructure()
elif sys.argv[1] == '--reset-user':
	if len(sys.argv) < 3:
		sys.exit(1)
	ldap.resetUser(sys.argv[2])
	
elif sys.argv[1] == '--reset-user-pw':
	if len(sys.argv) < 3:
		sys.exit(1)	
	ldap.resetUserPassword(sys.argv[2])
elif sys.argv[1] == '--reset-room':
	if len(sys.argv) < 3:
		sys.exit(1)	
	ldap.resetClassRoom(sys.argv[2])
	




