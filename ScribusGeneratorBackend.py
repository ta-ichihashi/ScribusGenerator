#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Mail-Merge for Scribus.
#
# For further information (manual, description, etc.) please visit:
# https://github.com/berteh/ScribusGenerator/
#
# v2.1 (2016-02-15): added support for repeating elements
# v2.0 (2015-12-02): added features (merge, range, clean, save/load)
# v1.9 (2015-08-03): initial command-line support (SLA only, use GUI version to generate PDF)
# v1.1 (2014-10-01): Add support for overwriting attributes from data (eg text/area color)
# v1.0 (2012-01-07): Fixed problems when using an ampersand as values within CSV-data.
# v2011-01-18: Changed run() so that scribus- and pdf file creation and deletion works without problems.
# v2011-01-17: Fixed the ampersand ('&') problem. It now can be used within variables.
# v2011-01-01: Initial Release.
#
"""
The MIT License
Copyright (c) 2010-2014 Ekkehard Will (www.ekkehardwill.de), 2014-2016 Berteh (https://github.com/berteh/)
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions: The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
"""
import csv
import os
import logging
import logging.config
import sys
import xml.etree.ElementTree as ET  # common Python xml implementation
import json
import re

class CONST:
    # Constants for general usage
    TRUE = 1
    FALSE = 0
    EMPTY = ''
    APP_NAME = 'Scribus Generator'
    APP_VERSION = '2.1'
    FORMAT_PDF = 'PDF'
    FORMAT_SLA = 'Scribus'
    FILE_EXTENSION_PDF = 'pdf'
    FILE_EXTENSION_SCRIBUS = 'sla'
    SEP_PATH = '/'  # In any case we use '/' as path separator on any platform
    SEP_EXT = os.extsep    
    CSV_SEP = "," # CSV entry separator, comma by default
    CONTRIB_TEXT = "\npowered by ScribusGenerator - https://github.com/berteh/ScribusGenerator/"
    STORAGE_NAME = "ScribusGeneratorDefaultSettings"
    REMOVE_EMPTY_LINES = 1 # set to 0 to preserve un-subsituted variables to be removed, along with their empty containing itext and pageobject
    REPEAT_FIELDS = 1 # set to 0 to NOT duplicate objects named "SGrepeat_*" for each data entry in the same document.

    
class ScribusGenerator:
    # The Generator Module has all the logic and will do all the work
    def __init__(self, dataObject):
        self.__dataObject = dataObject
        logging.config.fileConfig("logging.conf")
        logging.debug("ScribusGenerator initialized, v%s"%(CONST.APP_VERSION))

    
    def run(self):
        # Read CSV data and replace the variables in the Scribus File with the cooresponding data. Finaly export to the specified format.
        # may throw exceptions if errors are met, use traceback to get all error details
        
        #defaults for missing info
        if(self.__dataObject.getSingleOutput() and (self.__dataObject.getOutputFileName() is CONST.EMPTY)):
            self.__dataObject.setOutputFileName(os.path.split(os.path.splitext(self.__dataObject.getScribusSourceFile())[0])[1] +'__single')    

        #parsing
        logging.debug("parsing data source file %s"%(self.__dataObject.getDataSourceFile()))
        csvData = self.getCsvData(self.__dataObject.getDataSourceFile())
        if(len(csvData) < 1):
            logging.error("Data file %s is empty. At least a header line and a line of data is needed. Halting."%(self.__dataObject.getDataSourceFile()))
            return -1
        if(len(csvData) < 2):
            logging.error("Data file %s has only one line. At least a header line and a line of data is needed. Halting."%(self.__dataObject.getDataSourceFile()))
            return -1

        #range
        firstElement = 1
        if(self.__dataObject.getFirstRow() != CONST.EMPTY):
            try:
                newFirstElementValue = int(self.__dataObject.getFirstRow())
                firstElement = max(newFirstElementValue, 1) # Guard against 0 or negative numbers
            except:
                logging.warning("Could not parse value of 'first row' as an integer, using default value instead")
        lastElement = len(csvData)
        if(self.__dataObject.getLastRow() != CONST.EMPTY):
            try:
                newLastElementValue = int(self.__dataObject.getLastRow())
                lastElement = min(newLastElementValue + 1, lastElement) # Guard against numbers higher than the length of csvData
            except:
                logging.warning("Could not parse value of 'last row' as an integer, using default value instead")       
        if ( (firstElement != 1) or (lastElement != len(csvData)) ):
            csvData = csvData[0:1] + csvData[firstElement : lastElement]

        #generation
        dataC = len(csvData)-1
        fillCount = len(str(dataC))
        template = [] # XML-Content/Text-Content of the Source Scribus File (List of Lines)
        outputFileNames = []
        index = 0
        # Generate the Scribus Files
        for row in csvData:
            if(index == 0): # first line is the Header-Row of the CSV-File                
                headerRowForFileName = row
                headerRowForReplacingVariables = self.handleAmpersand(row) # Header-Row contains the variable names
                # overwrite attributes from their /*/ItemAttribute[Type=SGAttribute] sibling, when applicable.
                logging.debug("parsing scribus source file %s"%(self.__dataObject.getScribusSourceFile()))
                tree = ET.parse(self.__dataObject.getScribusSourceFile())
                root = tree.getroot()                
                templateElt = self.overwriteAttributesFromSGAttributes(root) # replace scribus xml attributes by dynamic variable name

                #save settings
                if(self.__dataObject.getSaveSettings()):
                	serial=self.__dataObject.toString()                    
                	logging.debug("saving current Scribus Generator settings in your source file")# as: %s"%serial)                    
                	docElt = root.find('DOCUMENT')                    
                	storageElt = docElt.find('./JAVA[@NAME="'+CONST.STORAGE_NAME+'"]')                    
                	if(storageElt is None):
                		colorElt = docElt.find('./COLOR[1]')                     
                		scriptPos = docElt.getchildren().index(colorElt)
                		logging.debug("creating new storage element in SLA template at position %s"%scriptPos)
                		storageElt = ET.Element("JAVA", {"NAME":CONST.STORAGE_NAME})
                		docElt.insert(scriptPos, storageElt)
                	storageElt.set("SCRIPT",serial)
                	tree.write(self.__dataObject.getScribusSourceFile()) #todo check if scribus reloads (or overwrites :/ ) when doc is opened, opt use API to add a script if there's an open doc.
                
                #detecting elements to be repeated (@ANNAME="SGrepeat_*")
                # pattern is [Dx]D[_dm][_dm][_t]" with D=direction[RLUD] x= # of steps in preceding D, d = direction[rlud], m = margin in preceding d, t = trash (distinct objects need distinct names)
                if(CONST.REPEAT_FIELDS == 1):
                	logging.debug("detecting & generating repeating elements")
                	pobjects = templateElt.findall('.//PAGEOBJECT[@ANNAME]') # ET does not support regexp
                	p = re.compile('SGrepeat\_([RLUD])(\d+)?(\_([RLUD]))?(\_([rlud])(\d+))?(\_([rlud])(\d+))?(.+)')
                	c = 0
                	for po in pobjects:
                		m = p.match(po.get('ANNAME'))
	                	if m:
	                		logging.debug("found 1 repeating element: %s"%(m.group(1,2,4,6,7,9,10),))
	                		c += 1
	                		(dir1, limit1, dir2, marginDir1, margin1, marginDir2, margin2) = m.group(1,2,4,6,7,9,10)	                		
	                		self.expandRepeatingObject(headerRowForReplacingVariables, csvData, po, templateElt, dir1, limit1, dir2, marginDir1, margin1, marginDir2, margin2)
	                
	                logging.debug("expanded %d repeating elements, exiting prematurely."%c)	                
	                return 1
	                
            else: # not the first (header) row -> replace variables with current data line
                outContent = self.replaceVariablesWithCsvData(headerRowForReplacingVariables, self.handleAmpersand(row), ET.tostringlist(templateElt))
                if (self.__dataObject.getSingleOutput()):
                    if (index == 1):
                        logging.debug("generating reference document from row #1")                        
                        outputElt = ET.fromstring(outContent)
                        docElt = outputElt.find('DOCUMENT')  
                        pagescount = int(docElt.get('ANZPAGES'))
                        pageheight = float(docElt.get('PAGEHEIGHT'))
                        vgap = float(docElt.get('GapVertical'))
                        groupscount = int(docElt.get('GROUPC'))
                        objscount = len(outputElt.findall('.//PAGEOBJECT'))
                        logging.debug("current template has #%s pageobjects"%(objscount))
                        version = outputElt.get('Version')
#                        if version.startswith('1.4'):
#                            docElt.set('GROUPC', str(groupscount*dataC))
                        docElt.set('ANZPAGES', str(pagescount*dataC))                        
                        docElt.set('DOCCONTRIB',docElt.get('DOCCONTRIB')+CONST.CONTRIB_TEXT)
                    else:
                        logging.debug("merging content from row #%s"%(index))
                        tmpElt = ET.fromstring(outContent).find('DOCUMENT')
                        shiftedElts = self.shiftPagesAndObjects(tmpElt, pagescount, pageheight, vgap, index-1, groupscount, objscount, version)                        
                        docElt.extend(shiftedElts)                                                
                else: # write one of multiple sla
                    outputFileName = self.createOutputFileName(index, self.__dataObject.getOutputFileName(), headerRowForFileName, row, fillCount)                    
                    self.writeSLA(ET.fromstring(outContent), outputFileName)
                    outputFileNames.append(outputFileName)                    
            index = index + 1
        
        # clean & write single sla
        if (self.__dataObject.getSingleOutput()):            
            self.writeSLA(outputElt, self.__dataObject.getOutputFileName())
            outputFileNames.append(self.__dataObject.getOutputFileName())        

        # Export the generated Scribus Files as PDF
        if(CONST.FORMAT_PDF == self.__dataObject.getOutputFormat()):
            for outputFileName in outputFileNames:
                pdfOutputFilePath = self.createOutputFilePath(self.__dataObject.getOutputDirectory(), outputFileName, CONST.FILE_EXTENSION_PDF)
                scribusOutputFilePath = self.createOutputFilePath(self.__dataObject.getOutputDirectory(), outputFileName, CONST.FILE_EXTENSION_SCRIBUS)
                self.exportPDF(scribusOutputFilePath, pdfOutputFilePath)
                logging.info("pdf file created: %s"%(pdfOutputFilePath))
        
        # Cleanup the generated Scribus Files
        if(not (CONST.FORMAT_SLA == self.__dataObject.getOutputFormat()) and CONST.FALSE == self.__dataObject.getKeepGeneratedScribusFiles()):
            for outputFileName in outputFileNames:
                scribusOutputFilePath = self.createOutputFilePath(self.__dataObject.getOutputDirectory(), outputFileName, CONST.FILE_EXTENSION_SCRIBUS)
                self.deleteFile(scribusOutputFilePath)

        return 1;
      
            

    def exportPDF(self, scribusFilePath, pdfFilePath):
        import scribus
        
        d = os.path.dirname(pdfFilePath)
        if not os.path.exists(d):
            os.makedirs(d)
      
        # Export to PDF
        scribus.openDoc(scribusFilePath)
        listOfPages = []
        i = 0
        while (i < scribus.pageCount()):
            i = i + 1
            listOfPages.append(i)
            
        pdfExport = scribus.PDFfile()
        pdfExport.info = CONST.APP_NAME
        pdfExport.file = str(pdfFilePath)
        pdfExport.pages = listOfPages
        pdfExport.save()
        scribus.closeDoc()

    def writeSLA(self, slaET, outFileName, clean=CONST.REMOVE_EMPTY_LINES):
        # write SLA to filepath computed from given elements, optionnaly cleaning empty ITEXT elements and their empty PAGEOBJECTS
        scribusOutputFilePath = self.createOutputFilePath(self.__dataObject.getOutputDirectory(), outFileName, CONST.FILE_EXTENSION_SCRIBUS)
        d = os.path.dirname(scribusOutputFilePath)
        if not os.path.exists(d):
            os.makedirs(d)
        outTree = ET.ElementTree(slaET) 
        if (clean):
            self.removeEmptyTexts(outTree.getroot())
        outTree.write(scribusOutputFilePath, encoding="UTF-8")
        logging.info("scribus file created: %s"%(scribusOutputFilePath)) 
        return scribusOutputFilePath


    def overwriteAttributesFromSGAttributes(self, root):
        # modifies root such that
        # attributes have been rewritten from their /*/ItemAttribute[Type=SGAttribute] sibling, when applicable.
        #
        # allows to use %VAR_<var-name>% in Item Attribute to overwrite internal attributes (eg FONT)   

        for pageobject in root.findall(".//ItemAttribute[@Type='SGAttribute']/../.."):
            sga = pageobject.find(".//ItemAttribute[@Type='SGAttribute']")            
            attribute = sga.get('Name')            
            value = sga.get('Value')  
            param = sga.get('Parameter')
                  
            if param is "": # Cannot use 'default' on .get() as it is "" by default in SLA file.
                param = "." # target is pageobject by default. Cannot use ".|*" as not supported by ET.
            elif param.startswith("/"): # ET cannot use absolute path on element 
                param = "."+param 

            try:
                targets = pageobject.findall(param)
                if targets :
                    for target in targets :
                        logging.debug('overwriting value of %s in %s with "%s"'%(attribute, target.tag, value))
                        target.set(attribute,value)
                else :
                    logging.error('Target "%s" could be parsed but designated no node. Check it out as it is probably not what you expected to replace %s.'%(param, attribute)) #todo message to user
                    
            except SyntaxError:
                logging.error('XPATH expression "%s" could not be parsed by ElementTree to overwrite %s. Skipping.'%(param, attribute)) #todo message to user

        return root


    def shiftPagesAndObjects(self, docElt, pagescount, pageheight, vgap, index, groupscount, objscount, version):
        shifted = []
        voffset = (float(pageheight)+float(vgap)) * index
        for page in docElt.findall('PAGE'):
            page.set('PAGEYPOS', str(float(page.get('PAGEYPOS')) + voffset))
            page.set('NUM', str(int(page.get('NUM')) + pagescount))
            shifted.append(page)
        for obj in docElt.findall('PAGEOBJECT'):
            obj.set('YPOS', str(float(obj.get('YPOS')) + voffset))
            obj.set('OwnPage', str(int(obj.get('OwnPage')) + pagescount))            
            #update ID and links
            if version.startswith('1.4'):
#                if not (int(obj.get('NUMGROUP')) == 0):
#                    obj.set('NUMGROUP', str(int(obj.get('NUMGROUP')) + groupscount * index))
                if (obj.get('NEXTITEM') != None and (str(obj.get('NEXTITEM')) != "-1")): # next linked frame by position                
                    obj.set('NEXTITEM', str(int(obj.get('NEXTITEM')) + (objscount * index)))
                if (obj.get('BACKITEM') != None and (str(obj.get('BACKITEM')) != "-1")): # previous linked frame by position
                    obj.set('BACKITEM', str(int(obj.get('BACKITEM')) + (objscount * index)))
            else : #1.5, 1.6
                logging.debug("shifting object %s (#%s)"%(obj.tag, obj.get('ItemID')))
                
                obj.set('ItemID', str(objscount * index) + str(int(obj.get('ItemID')))[3:] ) # update ID with something unlikely allocated, todo ensure unique ID.
                if (obj.get('NEXTITEM') != None and (str(obj.get('NEXTITEM')) != "-1")): # next linked frame by ItemID                       
                    obj.set('NEXTITEM', str(objscount * index) + str(int(obj.get('NEXTITEM')))[3:] )
                if (obj.get('BACKITEM') != None and (str(obj.get('BACKITEM')) != "-1")): # previous linked frame by ItemID    
                    obj.set('BACKITEM', str(objscount * index) + str(int(obj.get('BACKITEM')))[3:] )

            shifted.append(obj)
        logging.debug("shifted page %s element of %s"%(index,voffset))
        return shifted

    def removeEmptyTexts(self, root):
        # *modifies* root ElementTree by removing empty text elements and their empty placeholders.
        # returns number of ITEXT elements deleted.
        #   1. clean text in which some variable-like text is not substituted (ie: known or unknown variable):
        #      <ITEXT CH="empty %VAR_empty% variable should not show" FONT="Arial Regular" />
        #   2. remove <ITEXT> with empty @CH
        #   3. remove any <PAGEOBJECT> that has no <ITEXT> child left
        emptyXPath = "ITEXT[@CH='']"
        d = 0
        for page in root.findall(".//%s/../.." %emptyXPath): #little obscure because its parent is needed to remove an element, and ElementTree has no parent() method.
            for po in page.findall(".//%s/.." %emptyXPath):
                for emptyItext in po.findall("./%s" %emptyXPath):
                    logging.debug("cleaning 1 empty ITEXT")                    
                    po.remove(emptyItext)
                    d += 1
                if (len(po.findall("ITEXT")) is 0):
                    logging.debug("cleaning 1 empty PAGEOBJECT")
                    page.remove(po)                 
        logging.debug("removed %d empty ITEXTs"%d)
        return d

    
    # modifies root by appending copies of obj for each csvData row[1:], layout in grid per the various directions and margin parameters.
    def expandRepeatingObject(self, headerRow, csvData, obj, root, dir1='D', limitDir1=None, dir2=None, marginDir1=None, margin1=None, marginDir2=None, margin2=None):
	    #todo: make a string with all elements in po's group; substitute; shift; append; loop.
		logging.debug("expanding one object in direction %s. \nNOT IMPLEMENTED YET"%dir1)
		
		# establish reference element(s)
		template = ET.tostring(obj) #simple objects in v1.4, complete group in v1.5
		
		if(obj.get('isGroupControl') == "1"): #group in v1.4 #v1.4
			groupN = obj.get('NUMGROUP')
			logging.debug("collecting all objects of group %s" %groupN)
			for o in root.findall(".//PAGEOBJECT[@NUMGROUP='%s']" %groupN):
				template += ET.tostring(o)
		#logging.debug("full template to be duplicated below:\n%s"%template)
		
		#todo HERE shift %index.mod(limit) & substitute		
		#outContent = self.replaceVariablesWithCsvData(headerRow, self.handleAmpersand(row), ET.tostringlist(templateElt))

    
    def deleteFile(self, outputFilePath):
        # Delete the temporarily generated files from off the file system
        os.remove(outputFilePath)

    def createOutputFilePath(self, outputDirectory, outputFileName, fileExtension):
        # Build the absolute path, like C:/tmp/template.sla
        return outputDirectory + CONST.SEP_PATH + outputFileName + CONST.SEP_EXT + fileExtension
    
    def createOutputFileName(self, index, outputFileName, headerRow, row, fillCount):
        # If the User has not set an Output File Name, an internal unique file name
        # will be generated which is the index of the loop.
        result = str(index)
        result = result.zfill(fillCount)
        # Following characters are not allowed for File-Names on WINDOWS: < > ? " : | \ / *
        if(CONST.EMPTY != outputFileName):
                table = {
                         #ord(u'ä'): u'ae',
                         #ord(u'Ä'): u'Ae',
                         #ord(u'ö'): u'oe',
                         #ord(u'Ö'): u'Oe',
                         #ord(u'ü'): u'ue',
                         #ord(u'Ü'): u'Ue',
                         #ord(u'ß'): u'ss',
                         ord(u'<'): u'_',
                         ord(u'>'): u'_',
                         ord(u'?'): u'_',
                         ord(u'"'): u'_',
                         ord(u':'): u'_',
                         ord(u'|'): u'_',
                         ord(u'\\'): u'_',
                         ord(u'/'): u'_',
                         ord(u'*'): u'_'
                     }
                result = self.replaceVariablesWithCsvData(headerRow, row, [outputFileName])
                result = result.decode('utf_8')
                result = result.translate(table)
        return result

    def copyScribusContent(self, src):
        # Returns a plain copy of src where src is expected to be a list (of text lines)
        result = []
        for line in src:
            result.append(line)
        return result

    def readFileContent(self, src):
        # Returns the list of lines (as strings) of the text-file
        tmp = open(src, 'r')
        result = tmp.readlines()
        tmp.close()
        return result
     
    def handleAmpersand(self, row):
        # If someone uses an '&' as variable (e.g. %VAR_&position%), this text will be saved
        # like %VAR_&amp;position% as the & is being converted by scribus to textual ampersand.
        # Therefore we have to check and convert. It will also be used to replace ampersand of
        # CSV rows, so that you can have values like e.g. "A & B Company".
        result = []
        for i in row:
            result.append(i.replace('&', '&amp;'))
        return result
    
    
    def replaceVariablesWithCsvData(self, headerRow, row, lines, clean=CONST.REMOVE_EMPTY_LINES): # lines as list of strings
        result = ''
        for line in lines: # done in string instead of XML for lack of efficient attribute-value-based substring-search in ElementTree
            i = 0
            for cell in row:
                tmp = ('%VAR_' + headerRow[i] + '%')
                #do not substitute in colors definition, find something more efficient
                if (not(line.strip().startswith('<COLOR '))): # TODO fix this detection does not work on 1.5.1svn SLA file
                    line = line.replace(tmp, cell) # string.replace(old, new)
                i = i + 1
            if (clean):
                #remove (& trim) any %VAR_\w*% like string.                
                (line, d) = re.subn(r"\s*%VAR_\w*%\s*", "", line)
                if (d>0):
                    logging.debug("cleaned %d empty variable"%d)
            result = result + line
        return result
         
    def getCsvData(self, csvfile):
        # Read CSV file and return  2-dimensional list containing the data
        reader = csv.reader(file(csvfile), delimiter=self.__dataObject.getCsvSeparator())
        result = []
        for row in reader:
            rowlist = []
            for col in row:
                rowlist.append(col)
            result.append(rowlist)
        return result  

    def getLog(self):
        return logging

    def getSavedSettings(self):
        logging.debug("parsing scribus source file %s for user settings"%(self.__dataObject.getScribusSourceFile()))
        try:
            t = ET.parse(self.__dataObject.getScribusSourceFile())
            r = t.getroot()        
            doc = r.find('DOCUMENT')
            storage = doc.find('./JAVA[@NAME="'+CONST.STORAGE_NAME+'"]')                    
            return storage.get("SCRIPT")
        except Exception, e:
            logging.debug("could not load the user settings for Scribus Generator, skipping. more info:\n%s"%e.message)  
            return None
        
        

class GeneratorDataObject:
    # Data Object for transfering the settings made by the user on the UI / CLI
    def __init__(self,
        scribusSourceFile = CONST.EMPTY,
        dataSourceFile = CONST.EMPTY,
        outputDirectory = CONST.EMPTY,
        outputFileName = CONST.EMPTY,
        outputFormat = CONST.EMPTY,
        keepGeneratedScribusFiles = CONST.FALSE,
        csvSeparator = CONST.CSV_SEP,
        singleOutput = CONST.FALSE, 
        firstRow = CONST.EMPTY, 
        lastRow = CONST.EMPTY,
        saveSettings = CONST.TRUE):
        self.__scribusSourceFile = scribusSourceFile
        self.__dataSourceFile = dataSourceFile
        self.__outputDirectory = outputDirectory
        self.__outputFileName = outputFileName
        self.__outputFormat = outputFormat
        self.__keepGeneratedScribusFiles = keepGeneratedScribusFiles
        self.__csvSeparator = csvSeparator
        self.__singleOutput = singleOutput
        self.__firstRow = firstRow
        self.__lastRow = lastRow
        self.__saveSettings = saveSettings
    
    # Get
    def getScribusSourceFile(self):
        return self.__scribusSourceFile
    
    def getDataSourceFile(self):
        return self.__dataSourceFile
    
    def getOutputDirectory(self):
        return self.__outputDirectory
    
    def getOutputFileName(self):
        return self.__outputFileName
    
    def getOutputFormat(self):
        return self.__outputFormat
    
    def getKeepGeneratedScribusFiles(self):
        return self.__keepGeneratedScribusFiles

    def getCsvSeparator(self):
        return self.__csvSeparator

    def getSingleOutput(self):
        return self.__singleOutput

    def getFirstRow(self):
        return self.__firstRow

    def getLastRow(self):
        return self.__lastRow

    def getSaveSettings(self):
        return self.__saveSettings

    # Set
    def setScribusSourceFile(self, fileName):
        self.__scribusSourceFile = fileName
        
    def setDataSourceFile(self, fileName):
        self.__dataSourceFile = fileName
    
    def setOutputDirectory(self, directory):
        self.__outputDirectory = directory
        
    def setOutputFileName(self, fileName):
        self.__outputFileName = fileName
        
    def setOutputFormat(self, outputFormat):
        self.__outputFormat = outputFormat
        
    def setKeepGeneratedScribusFiles(self, value):
        self.__keepGeneratedScribusFiles = value

    def setCsvSeparator(self, value):
        self.__csvSeparator = value

    def setSingleOutput(self, value):
        self.__singleOutput = value

    def setFirstRow(self, value):
        self.__firstRow = value

    def setLastRow(self, value):
        self.__lastRow = value

    def setSaveSettings(self, value):
        self.__saveSettings = value

    # (de)Serialize all options but scribusSourceFile and saveSettings
    def toString(self):
        return json.dumps({
            '_comment':"this is an automated placeholder for ScribusGenerator default settings. more info at https://github.com/berteh/ScribusGenerator/. modify at your own risks.",
            #'scribusfile':self.__scribusSourceFile NOT saved
            'csvfile':self.__dataSourceFile,
            'outdir':self.__outputDirectory,
            'outname':self.__outputFileName,
            'outformat':self.__outputFormat,
            'keepsla':self.__keepGeneratedScribusFiles,
            'separator':self.__csvSeparator,
            'single':self.__singleOutput,
            'from':self.__firstRow,
            'to':self.__lastRow,
            #'savesettings':self.__saveSettings NOT saved
        }, sort_keys=True)

    def loadFromString(self, string): #todo add validity/plausibility checks on all values? 
        j = json.loads(string)
        for k,v in j.iteritems():
            if v == None:
                j[k] = CONST.EMPTY
        #self.__scribusSourceFile NOT loaded
        self.__dataSourceFile = j['csvfile']
        self.__outputDirectory = j['outdir']
        self.__outputFileName = j['outname']
        self.__outputFormat = j['outformat']
        self.__keepGeneratedScribusFiles = j['keepsla']
        self.__csvSeparator = str(j['separator']) #str()to prevent TypeError: : "delimiter" must be string, not unicode, in csv.reader() call
        self.__singleOutput = j["single"]
        self.__firstRow = j["from"]
        self.__lastRow = j["to"]
        # self.__saveSettings NOT loaded
        logging.debug("loaded %d user settings"%(len(j)-1)) #-1 for the artificial "comment"
        return j
