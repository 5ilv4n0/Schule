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
import sys, os, json
parameters = sys.argv[1:]
if len(parameters) < 1:
    parameters.append('parameter')


def getMaxLength(values):
    length = 0
    for entry in values:
        if len(entry)>length:
            length = len(entry)
    return length

def joinToString(strings, seperator=' '):
    return seperator.join(strings)

def replaceSpezialChars(value):
    value = value.replace('ä','ae')
    value = value.replace('Ä','Ae')
    value = value.replace('ö','oe')
    value = value.replace('Ö','Oe')
    value = value.replace('ü','ue')    
    value = value.replace('Ü','Ue')
    value = value.replace('ß','ss')   
    return value

def readJsonFile(filePath):
    if not os.path.isfile(filePath):
        clearJsonFile(filePath)

    with open(filePath) as jsonFile:
        try:
            jsonContent = json.load(jsonFile)
            return jsonContent
        except ValueError:
            print 'Datei nicht im JSON-Format. Bitte korrigieren.'
            sys.exit(1)

def writeJsonFile(filePath, jsonEncoded):
    jsonContent = json.dumps(jsonEncoded, indent=4)    
    with open(filePath,'w') as jsonFile:
        jsonFile.write(jsonContent)

def clearJsonFile(filePath):
    jsonEncoded = {}
    jsonEncoded['groups'] = []
    jsonEncoded['users'] = {}
    jsonContent = json.dumps(jsonEncoded, indent=4)    
    with open(filePath,'w') as jsonFile:
        jsonFile.write(jsonContent)




def newGroup(userAndGroupFilePath):
    usersAndGroups  = readJsonFile(userAndGroupFilePath)    
    groups          = usersAndGroups['groups']    
    group           = inputGroupWhileExists(groups)

    usersAndGroups['groups'].append(group)

    writeJsonFile(userAndGroupFilePath, usersAndGroups)

def delGroup(userAndGroupFilePath):
    usersAndGroups  = readJsonFile(userAndGroupFilePath)
    users           = usersAndGroups['users']
    groups          = usersAndGroups['groups']

    print "Warnung! Alle Benutzer der eingegebenen Gruppe werden ebenfalls entfernt!"
    print "Abbrechen mit <strg>-<c>"
    print
    group           = replaceSpezialChars(raw_input('Gruppe: '))

    for user in users.keys():
        if group in users[user]['groups']:
            del usersAndGroups['users'][user]
    del usersAndGroups['groups'][getGroupID(groups, group)]
    writeJsonFile(userAndGroupFilePath, usersAndGroups)    

def getGroupID(groups, name):
    for ID, group in enumerate(groups):
        if group == name:
            return ID
    return False

def newUser(userAndGroupFilePath):
    usersAndGroups  = readJsonFile(userAndGroupFilePath)    
    users           = usersAndGroups['users']
    groups          = usersAndGroups['groups']

    userName        = inputNameWhileExists(users.keys())
    groups          = inputGroups(groups)
    description     = raw_input('Beschreibung: ')

    usersAndGroups['users'][userName]                   = {}
    usersAndGroups['users'][userName]['groups']         = groups
    usersAndGroups['users'][userName]['description']    = description

    writeJsonFile(userAndGroupFilePath, usersAndGroups)

def delUser(userAndGroupFilePath):
    usersAndGroups  = readJsonFile(userAndGroupFilePath)    
    users           = usersAndGroups['users']
    groups          = usersAndGroups['groups']
    userName        = replaceSpezialChars(raw_input('Name: '))
    del usersAndGroups['users'][userName]
    writeJsonFile(userAndGroupFilePath, usersAndGroups)


def inputNameWhileExists(existsValueList):
    try:
        value = value
    except UnboundLocalError:
        value = None
    finally:
        while value in existsValueList or value == None:
            if not value == None:
                print joinToString(('Benutzer', '"' + value + '"', 'bereits vorhanden.'))
            value = raw_input(joinToString(('Name', ': '), ''))
            value = replaceSpezialChars(value)
        return value

def inputGroupWhileExists(existsValueList):
    try:
        value = value
    except UnboundLocalError:
        value = None
    finally:
        while value in existsValueList or value == None:
            if not value == None:
                print joinToString(('Gruppe', '"' + value + '"', 'bereits vorhanden.'))
            value = raw_input('Gruppe: ')
            value = replaceSpezialChars(value)
        return value

def inputGroups(groups):
    if len(groups) == 0:
        return None
    print 'Mögliche Gruppen:'
    print '+' + '-'*(getMaxLength(groups)-2+11) + '+'
    for ID, group in enumerate(groups):
        lineParts = ('| ', str(ID).rjust(4,' '), ' | ', group, ' '*(getMaxLength(groups)-len(group)), ' |')
        print joinToString(lineParts, '')
    print '+' + '-'*(getMaxLength(groups)-2+11) + '+'
    print 'Bitte die Gruppen-IDs kommagetrennt angeben!\n   z.B.: 1,2,5,7,10'
    groupIDs = raw_input('Gruppen-IDs: ')
    groupIDs = groupIDs.replace(' ','')
    groupIDs = groupIDs.split(',')
    userGroups = []
    for groupID in groupIDs:
        userGroups.append(groups[int(groupID)])
    return userGroups




userAndGroupFilePath    = 'database.json'
try:
    if parameters[0] == 'adduser':
        newUser(userAndGroupFilePath)
    elif parameters[0] == 'addgroup':
        newGroup(userAndGroupFilePath)
    elif parameters[0] == 'deletegroup':
        delGroup(userAndGroupFilePath)
    elif parameters[0] == 'deleteuser':
        delUser(userAndGroupFilePath)
    elif parameters[0] == '/?' or parameters[0] == '-?' or parameters[0] == '--help':
        print 
        print " - Benutzer- und Gruppenverwaltung - "
        print "-------------------------------------" 
        print " Beschreibung:"
        print '    Erstellt die Datenbankdatei "database.json", wenn diese nicht existert.'
        print '    Diese kann später unter Verwendung von "manageAD.py" in'
        print "    das Active Directory geschrieben werden."
        print "    Die Datenbankdatei ist im JSON-Format geschrieben."
        print "    Weitere Informationen zum Thema JSON finden Sie unter:"
        print "    http://de.wikipedia.org/wiki/JavaScript_Object_Notation"
        print
        print " Syntax: UserGroup.py <Befehl>"
        print 
        print "    Mögliche Befehle:"
        print "       addgroup       -> Legt eine Gruppe an."
        print "       adduser        -> Legt einen Benutzer an."
        print "       deletegroup    -> Entfernt eine Gruppe und deren Benutzer."
        print "       deleteuser     -> Entfernt einen Benutzer."
        print 
        print " Optionen:"
        print "    /?                -> Diese Ausgabe."
        print "    -?"
        print "    --help"
        print 
except KeyboardInterrupt:
    print '\nAbgebrochen.'
    sys.exit(0)


