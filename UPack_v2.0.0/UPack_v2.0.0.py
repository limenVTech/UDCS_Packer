#!/usr/local/bin/python3
"""
====================================================================
UDCS Packer (U-Pack)
for the Unified Digital Curation System (UDCS)
Written by L. I. Menzies, Digital Preservation Technologist
Digital Imaging & Preservation Services
Virginia Polytechnic Institute and State University
560 Drillfield Drive
Blacksburg, Virginia 24061

Created 2018-05-01 as "UDOF" by L. I. Menzies
This Version Last Updated 2019-06-27 by L. I. Menzies

====================================================================
This application is designed to do the following:
    (a) Creates minimal metadata files for each object in the target
        directory, as CSV, RDF-XML (and JSON-LD)
    (b) Registers the objects in the UDCS: Retrieves UUID's from the
        system naming authority, Assigns them to the digital objects,
        Logs these in a Processing Log, and Creates place-holder
        metadata records on the UDCS Metadata Server
    (d) Runs an inventory of each item and generates human-readable
        'manifest.csv' files within each object, containing SHA3-256
        checksum hashes, directory trees, and some technical metadata
    (e) Bags each object, according to BagIt formatting structure,
        and generates BagIt checksum files using SHA2-512
    (f) Creates a TAR "archive" of each object (GZip is optional)
        NOTE: Gzip compress the Tar file. The use of this feature for
            preservation follows the Spatial Data Transfer Standard's
            (SDTS) use of 'tar.gz'.
    (g) Generates a transfer manifest of a directory, as a CSV list of
        filenames and checksums, in preparation for their transfer to
        Preservation as Submission Information Packages (SIP).
====================================================================
For more information, see the DI&PS collaboration wiki:
https://webapps.es.vt.edu/confluence/display/DIPS/Instructions+for+Using+the+U-Pack+Tool
or contact L. I. Menzies = limen (at) vt (dot) edu
====================================================================
"""

import csv
import hashlib
import io
import math
import mimetypes
import platform
import shutil
import sys
import tarfile
import time
import tkinter as tk
import uuid
from os import getcwd, listdir, mkdir, path, remove, rename, stat, walk
from tkinter import messagebox, Button, Entry, Label, Checkbutton, Frame, Toplevel, OptionMenu, Text, Scrollbar
from tkinter.filedialog import askdirectory, askopenfilename, StringVar, IntVar

import bagit
from PIL import Image, ImageTk
from rdflib import URIRef, Graph, BNode, Literal
from rdflib.namespace import *

""" Global color definitions, w/ official VT RGB values """
vtmaroon = '#%02x%02x%02x' % (134, 31, 65)
vtorange = '#%02x%02x%02x' % (232, 119, 34)
hokiestone = '#%02x%02x%02x' % (117, 120, 123)
vtwhite = '#%02x%02x%02x' % (255, 255, 255)
vtsmoke = '#%02x%02x%02x' % (229, 225, 230)
vtgray = '#%02x%02x%02x' % (215, 210, 203)

MY_OS = platform.system()


def resource_path(relative_path):
    """ Fixes the problem with PyInstaller not hooking associated files """
    base_path = getattr(sys, '_MEIPASS', path.dirname(path.abspath(__file__)))
    return path.join(base_path, relative_path)


class ToggleFrame(Frame):
    """ Creates a toggle frame for optional functions """

    def __init__(self, parent):
        Frame.__init__(self, parent)
        self.show = IntVar()
        self.show.set(0)
        #
        if MY_OS == 'Windows':
            xpad = 0
            ypad = 5
            basefont = 10
            spacepad = 152
        elif MY_OS == 'Linux':
            xpad = 7
            ypad = 5
            basefont = 12
            spacepad = 172
        else:
            xpad = 7
            ypad = 5
            basefont = 14
            spacepad = 175
        #
        self.show_frame = Frame(self)
        self.space = Label(self.show_frame, text='')
        self.space.configure(fg=hokiestone, bg=hokiestone, relief='flat')
        self.space.grid(column=0, row=0, pady=0, padx=spacepad, sticky='e')
        self.togButton = Checkbutton(self.show_frame, text='Show Options', command=self.tog_options, variable=self.show,
                                     fg='black', bg=hokiestone, bd=4, font=('Arial', basefont), justify='left')
        self.togButton.grid(column=1, row=0, pady=0, padx=xpad, sticky='w')
        self.prompt = IntVar()
        self.prompt.set(0)
        self.promptButton = Checkbutton(self.show_frame, text='Prompt after Each Action?', variable=self.prompt,
                                        fg='black', bg=hokiestone, bd=4, font=('Arial', basefont), justify='left')
        self.promptButton.grid(column=2, row=0, pady=0, padx=xpad, sticky='w')
        #
        self.sub_frame = Frame(self)
        labl4 = Label(self.sub_frame, text='Options:')
        labl4.configure(fg='black', bg=vtgray, bd=0, font=('Arial', basefont), height=2, width=9, justify='center')
        labl4.grid(column=0, row=0, pady=5, padx=5, sticky='w')
        # Options checkbuttons
        # Metadata
        self.metavar = IntVar(self.sub_frame)
        meta_chk = Checkbutton(self.sub_frame, text='Create min\nmetadata files', variable=self.metavar, fg='black',
                               bg=hokiestone, relief='flat', bd=4, font=('Arial', basefont), justify='left')
        meta_chk.grid(column=1, row=0, pady=5, padx=xpad)
        # Register objects
        self.regisvar = IntVar(self)
        regis_chk = Checkbutton(self.sub_frame, text='Register\nObjects', variable=self.regisvar, fg='black',
                                bg=hokiestone, relief='flat', bd=4, font=('Arial', basefont), justify='left')
        regis_chk.grid(column=2, row=0, pady=5, padx=xpad)
        # Inventory
        self.invenvar = IntVar(self)
        inv_chk = Checkbutton(self.sub_frame, text='Generate\n\'manifest.csv\'', variable=self.invenvar, fg='black',
                              bg=hokiestone, relief='flat', bd=4, font=('Arial', basefont), justify='left')
        inv_chk.grid(column=3, row=0, pady=5, padx=xpad)
        # BagIt
        self.bagitvar = IntVar(self)
        bagit_chk = Checkbutton(self.sub_frame, text='BagIt\n', variable=self.bagitvar, fg='black', bg=hokiestone,
                                relief='flat', bd=4, font=('Arial', basefont), justify='left')
        bagit_chk.grid(column=4, row=0, pady=5, padx=xpad)
        # Tar
        self.tarvar = IntVar(self)
        tar_chk = Checkbutton(self.sub_frame, text='TAR\nObjects', variable=self.tarvar, fg='black', bg=hokiestone,
                              relief='flat', bd=4, font=('Arial', basefont), justify='left')
        tar_chk.grid(column=5, row=0, pady=5, padx=xpad)
        # Transfer manifest
        self.transvar = IntVar(self)
        trans_chk = Checkbutton(self.sub_frame, text='Transfer\nManifest', variable=self.transvar, fg='black',
                                bg=hokiestone, relief='flat', bd=4, font=('Arial', basefont), justify='left')
        trans_chk.grid(column=6, row=0, pady=5, padx=xpad)
        # Set defaults to "checked"
        self.metavar.set(1)
        self.regisvar.set(1)
        self.invenvar.set(1)
        self.bagitvar.set(1)
        self.tarvar.set(1)
        self.transvar.set(1)
        #
        self.sub_frame.configure(bd=2, bg=hokiestone, relief='raised')
        self.show_frame.configure(bd=2, bg=hokiestone, relief='flat')
        self.show_frame.grid(column=0, row=3, pady=0, padx=0, sticky='nsew')

    def tog_options(self):
        if self.show.get() == 1:
            self.sub_frame.grid(column=0, row=0, pady=0, padx=0, sticky='nsew')
            self.togButton.configure(text='Hide Options')
        else:
            self.sub_frame.grid_forget()
            self.togButton.configure(text='Show Options')


class ObjFormatter:
    """ The main widget """

    def __init__(self, root):
        #
        if MY_OS == 'Windows':
            imgpad = 155
            xpadd = 5
            ypadd = 5
            basefont = 10
            entryfont = 11
            buttonpad = 202
        elif MY_OS == 'Linux':
            imgpad = 170
            xpadd = 5
            ypadd = 5
            basefont = 12
            entryfont = 14
            buttonpad = 210
        else:
            imgpad = 190
            xpadd = 5
            ypadd = 5
            basefont = 14
            entryfont = 16
            buttonpad = 210
        #
        # Main widget background image
        frame0 = Frame(root)
        logoimgpath = resource_path("UPackLogo300.jpg")
        logo = Image.open(logoimgpath)
        self.logoimage = ImageTk.PhotoImage(logo)
        self.logoimglabel = Label(frame0, image=self.logoimage)
        self.logoimglabel.configure(bg='black', bd=0, relief='flat')
        self.logoimglabel.grid(column=0, row=0, pady=7, padx=imgpad, sticky='e')
        frame0.configure(bg=hokiestone, bd=5, relief='sunken')
        frame0.grid(column=0, row=0, pady=0, padx=0, sticky='nsew')
        # Entry for the Folder that contains the items
        frame1 = Frame(root)
        itemfolder = StringVar(frame1)
        labl1 = Label(frame1, text='Folder of\nItems:')
        labl1.configure(fg='black', bg=vtgray, bd=0, font=('Arial', basefont), height=2, width=9, justify='center')
        labl1.grid(column=0, row=0, pady=5, padx=5, sticky='e')
        browse1 = Button(frame1, text='Browse', command=lambda: self.ask_folder(itemfolder))
        browse1.configure(bg=vtsmoke, fg='black', highlightbackground=vtmaroon, font=('Arial', entryfont))
        browse1.grid(column=2, row=0, pady=5, padx=5, sticky='w')
        self.e1 = Entry(frame1, width=50, textvariable=itemfolder)
        self.e1.configure(bg=vtsmoke, relief='sunken', bd=2, font=('Arial', entryfont + 2), justify='left')
        self.e1.grid(column=1, row=0, pady=5, padx=0, sticky='w')
        # Entry for the master CSV metadata file
        csvfile = StringVar(frame1)
        labl2 = Label(frame1, text='CSV File:')
        labl2.configure(fg='black', bg=vtgray, bd=0, font=('Arial', basefont), height=2, width=9, justify='center')
        labl2.grid(column=0, row=1, pady=5, padx=5, sticky='e')
        browse2 = Button(frame1, text='Browse', command=lambda: self.ask_file(csvfile))
        browse2.configure(bg=vtsmoke, fg='black', highlightbackground=vtmaroon, font=('Arial', entryfont),
                          relief='raised')
        browse2.grid(column=2, row=1, pady=5, padx=5, sticky='w')
        self.e2 = Entry(frame1, width=50, textvariable=csvfile)
        self.e2.configure(bg=vtsmoke, relief='sunken', bd=2, font=('Arial', entryfont + 2), justify='left')
        self.e2.grid(column=1, row=1, pady=5, padx=0, sticky='w')
        # Drop-Down of the column headings in the master CSV file
        labl3 = Label(frame1, text='CSV Col.\nw/ ID\'s:')
        labl3.configure(fg='black', bg=vtgray, bd=0, font=('Arial', basefont), height=2, width=9, justify='center')
        labl3.grid(column=0, row=2, pady=5, padx=5, sticky='e')
        self.variable = StringVar(frame1)
        self.options = StringVar(frame1)
        self.options.trace('r', self.get_headers)
        firstone = ["Select CSV", "Then \'Refresh\'"]
        self.hdmenu = OptionMenu(frame1, self.variable, *firstone)
        self.hdmenu.configure(width=20, bg=vtmaroon, font=('Arial', basefont + 2))
        self.hdmenu.grid(column=1, row=2, pady=5, padx=0, sticky='e')
        self.e3 = Entry(frame1, width=24, textvariable=self.variable)
        self.e3.configure(bg=vtsmoke, relief='sunken', bd=2, font=('Arial', entryfont + 2), justify='left')
        self.e3.grid(column=1, row=2, pady=5, padx=0, sticky='w')
        refresh1 = Button(frame1, text='Refresh', command=lambda: self.get_headers(csvfile))
        refresh1.configure(bg=vtsmoke, fg='black', highlightbackground=vtmaroon, font=('Arial', entryfont))
        refresh1.grid(column=2, row=2, pady=5, padx=5, sticky='w')
        frame1.configure(bg=vtmaroon, bd=5, relief='raised')
        frame1.grid(column=0, row=1, pady=0, padx=0, sticky='nsew')
        # Checkbuttons
        frame2 = ToggleFrame(root)
        frame2.configure(bg=hokiestone, bd=5, relief='sunken')
        frame2.grid(column=0, row=2, pady=0, padx=0, sticky='n')
        # Buttons for Quit, Instructions, and Submit
        frame3 = Frame(root)
        cancel1 = Button(frame3, text='Quit', command=root.quit)
        cancel1.configure(bg=vtwhite, fg='black', highlightbackground=vtmaroon, font=('Arial', entryfont))
        cancel1.grid(column=0, row=0, pady=5, padx=xpadd, sticky='e')
        instruct = Button(frame3, text='Instructions', command=lambda: instructions(basefont))
        instruct.configure(bg=vtwhite, fg='black', highlightbackground=vtmaroon, font=('Arial', entryfont))
        instruct.grid(column=1, row=0, pady=5, padx=buttonpad, sticky='e')
        submit1 = Button(frame3, text='Submit', command=lambda: self.run_procs(root, frame2))
        submit1.configure(bg=vtwhite, fg='black', highlightbackground=vtmaroon, font=('Arial', entryfont))
        submit1.grid(column=2, row=0, pady=5, padx=xpadd, sticky='e')
        frame3.configure(bg=vtmaroon, bd=5, relief='raised')
        frame3.grid(column=0, row=3, pady=0, padx=0, sticky='nsew')

    def ask_folder(self, foname):
        foname.set(path.abspath(askdirectory(initialdir=getcwd(), title='Select the Folder')))
        return foname

    def ask_file(self, fname):
        fname.set(path.abspath(askopenfilename(initialdir=getcwd(), title='Select the master CSV File')))
        return fname

    def get_headers(self, *args):
        """ Retrieves the options for the drop-down menu of CSV headers """
        csvfi = self.e2.get()
        csvpath = path.join(str(csvfi))
        if path.exists(csvpath) and path.splitext(csvpath)[1] == '.csv':
            with open(csvfi, 'r', encoding='utf-8') as cfile:
                hreader = csv.DictReader(cfile)
                opts = hreader.fieldnames
        else:
            opts = ["Select CSV", "Then \'Refresh\'"]
        self.variable.set(opts[0])
        menu = self.hdmenu['menu']
        menu.delete(0, 'end')
        for headr in opts:
            menu.add_command(label=headr, command=lambda idcolumn=headr: self.variable.set(idcolumn))

    def make_rdf(self, metacsv):
        """
        Turns 'metadata.csv' into an RDF metadata file, called 'metadata.xml'
        This could be done using a CSV-to-XML conversion, but it's easier to
        just read the values for the fields and write the RDF file manually.
        """
        if not path.exists(metacsv):
            messagebox.showwarning(message="Error: The \'metadata.csv\' was not found.\nRDF file not created.")
            return False
        with open(metacsv, 'r', encoding='utf-8') as src:
            reader2 = csv.DictReader(src)
            headrow2 = reader2.fieldnames
            for row in reader2:
                sysUUID = str(row['System UUID'])
                localID = str(row['Local ID'])
                deptName = str(row['Department Responsible'])
                persVTID = str(row['Person Responsible'])
                collName = str(row['Collection'])
                description = str(row['Brief Description'])
                objURI = str(row['Object URI'])
                collURI = str(row['Collection URI'])
        src.close()
        # messagebox.showwarning(message="It got this far! Next step is create the Graph.")
        g = Graph()
        # Namespaces
        rdf = Namespace("http://www.w3.org/1999/02/22-rdf-syntax-ns#")
        g.bind('rdf', rdf, False)
        rdfs = Namespace("http://www.w3.org/2000/01/rdf-schema#")
        g.bind('rdfs', rdfs, False)
        dc = Namespace("http://dublincore.org/2012/06/14/dcelements.rdf#")
        g.bind('dc', dc, False)
        dcterms = Namespace("http://purl.org/dc/terms#")
        g.bind('dcterms', dcterms, False)
        dcmitype = Namespace("http://purl.org/dc/dcmitype#")
        g.bind('dcmitype', dcmitype, False)
        foaf = Namespace("http://xmlns.com/foaf/spec/index.rdf#")
        g.bind('foaf', foaf, False)
        owl = Namespace("http://www.w3.org/2002/07/owl#")
        g.bind('owl', owl, False)
        premis = Namespace("http://www.loc.gov/premis/rdf/v3#")
        g.bind('premis', premis, False)
        mets = Namespace("http://www.loc.gov/standards/mets/mets.xsd#")
        g.bind('mets', mets, False)
        # Establishing subjects for triples
        object = URIRef(objURI)
        persID = BNode()
        g.bind('personID', persID, False)
        deptID = BNode()
        g.bind('departmentID', deptID, False)
        collectID = URIRef(collURI)
        g.bind('collectionID', collectID, False)
        metsCustodian = URIRef('http://www.loc.gov/standards/mets/mets.xsd#CUSTODIAN')
        g.bind('custodian', metsCustodian, False)
        # Adding the triples to the Graph
        g.add((object, dcterms.identifier, Literal('%s' % sysUUID)))
        g.add((object, mets.OBJID, Literal('%s' % sysUUID)))
        g.add((object, mets.altRecordID, Literal('%s' % localID)))
        g.add((object, dc.contributor, deptID))
        g.add((deptID, rdf.type, foaf.Group))
        g.add((deptID, mets.ROLE, metsCustodian))
        g.add((deptID, foaf.name, Literal('%s' % deptName)))
        g.add((object, dc.contributor, persID))
        g.add((persID, rdf.type, foaf.Person))
        g.add((persID, mets.ROLE, metsCustodian))
        g.add((persID, foaf.mbox, Literal('%s (at) vt (dot) edu' % persVTID)))
        # g.add((persID, foaf.name, Literal('%s' %persName)))
        g.add((object, dcterms.isPartOf, collectID))
        g.add((collectID, foaf.name, Literal('%s' % collName)))
        g.add((object, dcterms.description, Literal('%s' % description)))
        newrdf = path.join(path.dirname(metacsv), 'metadata.xml')
        serialrdf = g.serialize(format='pretty-xml')
        # serialjson = g.serialize(format='json-ld')
        with open(newrdf, 'wb') as outrdf:
            outrdf.write(serialrdf)
        outrdf.close()
        # jsonfile = path.join(path.dirname(metacsv), 'metadata.json')
        # with open(jsonfile, 'w', encoding='utf-8') as outjson:
        #     outjson.write(serialjson)
        # outjson.close()
        return True

    def meta_from_csv(self, csvIn, locids, fpath):
        nfiles = 0
        rfiles = 0
        overwrite_all = False
        firstone = True
        with open(csvIn, 'r', encoding='utf-8') as incsv:
            reader = csv.DictReader(incsv)
            headers = reader.fieldnames
            verifyHeadrs = ['System UUID', 'Local ID', 'Department Responsible', 'Person Responsible', 'Collection',
                            'Brief Description', 'Object URI', 'Collection URI']
            if not headers == verifyHeadrs:
                messagebox.showwarning(message="Your input CSV is not formatted correctly.\n\nQuitting action.")
                return [0, 0]
            for row in reader:
                skip1 = False
                foldname = row['%s' % locids]
                foldpath = path.join(fpath, foldname)
                if not path.exists(foldpath):
                    skip1 = True
                # The function skips objects that are Bags or already have a
                # 'metadata.csv' file. Thus it skips creating a 'metadata.xml'
                # for these objects also.
                if path.exists(path.join(foldpath, 'data')):
                    skip1 = messagebox.askyesno(
                        message="It appears that \'%s\' is a bag.\n\nSkip creating \'metadata.csv\' for this one item?" % foldname)
                if path.exists(path.join(foldpath, 'metadata.csv')) and firstone == True:
                    firstone = False
                    overwrite_all = messagebox.askyesno(
                        message="At least one \'metadata.csv\' already\nexists. Overwrite ALL of them?")
                if path.exists(path.join(foldpath, 'metadata.csv')) and overwrite_all == False:
                    skip1 = True
                if skip1 == False:
                    metafile = path.join(foldpath, 'metadata.csv')
                    with open(metafile, 'w') as newmeta:
                        metawriter = csv.DictWriter(newmeta, fieldnames=headers)
                        metawriter.writeheader()
                        metawriter.writerow(row)
                    nfiles += 1
                    newmeta.close()
                    rdfok = self.make_rdf(metafile)
                    if rdfok == True:
                        rfiles += 1
        return [nfiles, rfiles]

    def create_meta(self, root, folderpath, myfile, idcolname, moreopts1):
        """
        Generates minimal metadata files, 'metadata.csv' and 'metadata.xml'
        based on a master CSV or a METS xml file
        """
        sourcetype = 'csv'  # default
        counts = [0, 0]  # default
        if path.splitext(myfile)[1] == '.csv':
            sourcetype = 'csv'
        else:
            messagebox.showwarning(message="The metadata source file must be CSV.\nQuitting action.")
            runnext1 = False
            return runnext1
        if sourcetype == 'csv':
            counts = self.meta_from_csv(myfile, idcolname, folderpath)
        if not moreopts1 == 0:
            if self.prompting == 0:
                runnext1 = True
            else:
                runnext1 = messagebox.askyesno(
                    message="Created %d \'metadata.csv\' and %d \'metadata.xml\' files.\n\nProceed with the next action?" % (
                        counts[0], counts[1]))
        else:
            runnext1 = False
            messagebox.showwarning(
                message="Created %d \'metadata.csv\' and %d \'metadata.xml\' files." % (counts[0], counts[1]))
        return runnext1

    def gen_ID(self):
        """
        Function to generate a System UUID. In future this will request a NOID
        and ARK from the naming authority
        """
        SysUID = 'vtdata_' + str(uuid.uuid4())
        return SysUID

    def register_obj(self, ofolder, moreopts2):
        """
        Function to assign System UUID's to objects and register them in the UDCS
            (a) generate UUID from single naming authority
            (b) log the obj. in a system Processing Log
            (c) create placeholder metadata on the Metadata Server
            (d) update the minimal 'metadata' files with the System UUID
        """
        renamed = 0
        rfiles = 0
        logfile = path.join(ofolder, 'log4preservation.csv')
        if not path.exists(logfile):
            with open(logfile, 'w', encoding='utf-8') as lfile:
                headrow = ['SysUID', 'LocalID', 'RegisDateTime', 'RegisPerson']
                writer = csv.DictWriter(lfile, fieldnames=headrow)
                writer.writeheader()
            lfile.close()
        for fo in listdir(ofolder):
            skip3 = False
            fopath = path.join(ofolder, fo)
            if not path.isdir(fopath):
                skip3 = True
            elif path.isdir(fopath):
                metapath = path.join(fopath, 'metadata.csv')
                oldrdf = path.join(fopath, 'metadata.xml')
                # oldjson = path.join(fopath, 'metadata.json')
                if not path.exists(metapath):
                    skip3 = True
                    messagebox.showwarning(
                        message="Could not find:\n\'%s\'.\n\nSkipping registration of:\n%s." % (metapath, fo))
                if not skip3:
                    newID = self.gen_ID()
                    with open(metapath, 'r', encoding='utf-8') as oldmeta:
                        r = csv.reader(oldmeta)
                        lines = list(r)
                        lines[1][0] = newID
                        log1 = newID
                        log2 = lines[1][1]
                        log3 = time.strftime("%Y.%m.%d %H:%M:%S")
                        log4 = lines[1][3]
                        logline = [log1, log2, log3, log4]
                    with open(logfile, 'a', encoding='utf-8') as logoutf:
                        cwriter = csv.writer(logoutf)
                        cwriter.writerow(logline)
                    with open(metapath, 'w', encoding='utf-8') as outmeta:
                        w = csv.writer(outmeta)
                        w.writerows(lines)
                    if path.exists(oldrdf):
                        remove(oldrdf)
                    # if path.exists(oldjson):
                    #     remove(oldjson)
                    rdfok = self.make_rdf(metapath)
                    if rdfok == True:
                        rfiles += 1
                    newpath = path.join(path.dirname(fopath), '%s' % newID)
                    rename(fopath, newpath)
                    renamed += 1
        if not moreopts2 == 0:
            if self.prompting == 0:
                runnext2 = True
            else:
                runnext2 = messagebox.askyesno(
                    message="Registered %d objects.\n\nProceed with the next action?" % renamed)
        else:
            runnext2 = False
            messagebox.showwarning(message="Registered %d objects." % renamed)
        return runnext2

    def md5(self, finame):
        """ Data Services requested Md5 hashes but Md5 is deprecated """
        hash_md5 = hashlib.md5()
        with open(finame, "rb") as md5file:
            for chunk in iter(lambda: md5file.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()

    def sha3hash(self, filname):
        """ Generates SHA3-256 hashes """
        chunksize = io.DEFAULT_BUFFER_SIZE
        hash_sha3 = hashlib.sha3_256()
        with open(filname, "rb") as sha3file:
            for chunks in iter(lambda: sha3file.read(chunksize), b""):
                hash_sha3.update(chunks)
        return hash_sha3.hexdigest()

    def convert_size(self, size):
        """ Converts bytes to human readable denominations """
        if (size == 0):
            return '0B'
        # size_name = ("B", "KiB", "MiB", "GiB", "TiB", "PiB", "EiB", "ZiB", "YiB")
        # i = int(math.floor(math.log(size,1024)))
        # p = math.pow(1024,i)
        size_name = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
        i = int(math.floor(math.log(size, 1000)))
        p = math.pow(1000, i)
        s = round(size / p, 2)
        return '%s%s' % (s, size_name[i])

    def run_inventory(self, indir, moreopts3):
        """
        Runs an inventory and generates 'manifest.csv' files for each object
        """
        manifiles = 0
        for obj in listdir(indir):
            objpath = path.join(indir, obj)
            skipit = False
            counter = 0
            if not path.isdir(objpath):
                skipit = True
            elif path.isdir(objpath):
                if path.exists(path.join(objpath, 'data')):
                    isabag = messagebox.askyesno(message="It appears that \'%s\' is a bag.\nSkip this object?" % obj)
                    if isabag == True:
                        skipit = True
                if path.exists(path.join(objpath, 'manifest.csv')):
                    skipit = True
                    messagebox.showwarning(
                        message="The file \'manifest.csv\' already exists.\nSkipping inventory of the object: \n\'%s\'" % obj)
            if skipit == False:
                manifiles += 1
                tempmani = open(path.join(indir, 'temp_manifest.csv'), 'w', encoding='utf-8')
                tempmani.write(
                    "No., Filename, Filesize, Filetype, C-Time, Modified, Accessed, MD5_Sum, SHA3_256, ChecksumDateTime, RelPath, => , mode, inode, device, enlink, user, group\n")
                workdir = path.dirname(objpath)
                for base, dirs, files in walk(objpath):
                    for name in files:
                        filepathname = path.join(base, name)
                        # Deletes .DS_Store Files
                        if path.basename(filepathname) == '.DS_Store':
                            remove(filepathname)
                        elif not path.basename(filepathname) == '.DS_Store':
                            counter += 1
                            rownum = str(counter)
                            statinfo = stat(filepathname)
                            filesize = statinfo[6]
                            csize = self.convert_size(filesize)
                            filemime = str(mimetypes.guess_type(filepathname)[0])
                            filectime = time.strftime("%Y.%m.%d %H:%M:%S", time.localtime(statinfo.st_ctime))
                            # note: on a Windows system, ctime is "date created" but on Unix it is
                            # "change time", i.e. the last time the metadata was changed.
                            modifdate = time.strftime("%Y.%m.%d %H:%M:%S", time.localtime(statinfo.st_mtime))
                            accessdate = time.strftime("%Y.%m.%d %H:%M:%S", time.localtime(statinfo.st_atime))
                            md5sum = self.md5(filepathname)
                            sha3sum = self.sha3hash(filepathname)
                            runtime = time.strftime("%Y.%m.%d %H:%M:%S")
                            filemode = str(statinfo.st_mode)
                            fileino = str(statinfo.st_ino)
                            filedevice = str(statinfo.st_dev)
                            filenlink = str(statinfo.st_nlink)
                            fileuser = str(statinfo.st_uid)
                            filegroup = str(statinfo.st_gid)
                            # Displays a shortened Path for each file, excluding the directories
                            # that precede the working directory that contains the objects.
                            showpath = path.relpath(filepathname, workdir)
                            tempmani.write(
                                "%s," % rownum + "\"%s\"," % name + "%s," % csize + "\"%s\"," % filemime + "%s," % filectime + "%s," % modifdate + "%s," % accessdate + "%s," % md5sum + "%s," % sha3sum + "%s," % runtime + "\"%s\"," % showpath)
                            tempmani.write(
                                " ,%s," % filemode + "%s," % fileino + "%s," % filedevice + "%s," % filenlink + "%s," % fileuser + "%s\n" % filegroup)
                tempmani.write("Comments, \n")
                tempmani.close()
                tomove = path.join(path.dirname(objpath), 'temp_manifest.csv')
                moveto = path.join(objpath, 'manifest.csv')
                shutil.move(tomove, moveto)
        if not moreopts3 == 0:
            if self.prompting == 0:
                runnext3 = True
            else:
                runnext3 = messagebox.askyesno(
                    message="Created %d \'manifest.csv\' files.\n\nProceed with the next action?" % manifiles)
        else:
            runnext3 = False
            messagebox.showwarning(message="Created %d \'manifest.csv\' files." % manifiles)
        return runnext3

    def run_bagit(self, bagsdir, moreopts4):
        """ Bags all objects in a single directory """
        validbags = 0
        totalbags = 0
        for f in listdir(bagsdir):
            inpath = path.join(bagsdir, f)
            cont = True
            if path.isdir(inpath):
                if path.exists(path.join(inpath, 'data')):
                    cont = messagebox.askyesno(message="It appears that \'%s\' is already a bag.\nBag it anyway?" % f)
                if cont == True:
                    newbag = bagit.make_bag(inpath, checksums=['md5', 'sha512'])
                    totalbags += 1
                    if newbag.is_valid():
                        validbags += 1
                    elif not newbag.is_valid():
                        messagebox.showwarning(message="Bag \'%s\' is not a valid bag." % f)
                # elif cont == False:
                #     messagebox.showwarning(message="Skipped bagging of \'%s\'." %f)
        if not moreopts4 == 0:
            if self.prompting == 0:
                runnext4 = True
            else:
                runnext4 = messagebox.askyesno(
                    message="Created %d total bags,\nof which %d are valid.\n\nProceed with the next action?" % (
                        totalbags, validbags))
        else:
            runnext4 = False
            messagebox.showwarning(message="Created %d total bags,\nof which %d are valid." % (totalbags, validbags))
        return runnext4

    def run_tar(self, tarfolder, moreopts5):
        """ Tars all objects in a single directory """
        tarfiles = 0
        alreadytar = 0
        notfolder = 0
        outfolder = path.splitext(tarfolder)[0] + '-tarred'
        if not path.exists(outfolder):
            mkdir(outfolder)
        for i in listdir(tarfolder):
            infile = path.join(tarfolder, i)
            if path.isdir(infile):
                outfile = path.join(outfolder, path.splitext(i)[0] + '.tar')
                if path.exists(outfile):
                    messagebox.showwarning(
                        message="The TAR file: \n\'%s\'\nalready exists!\nTar archive not created." % outfile)
                    alreadytar += 1
                elif not path.exists(outfile):
                    # with tarfile.open(outfile, 'w:gz') as newtar:
                    with tarfile.open(outfile, 'w') as newtar:
                        tarname = path.relpath(infile, tarfolder)
                        newtar.add(infile, arcname='%s' % tarname)
                    tarfiles += 1
            else:
                notfolder += 1
        if not alreadytar == 0:
            messagebox.showwarning(message="The folder \'%s\' already contained %d tar files which were skipped." % (
                outfolder, alreadytar))
        # if not notfolder == 0:
        #    messagebox.showwarning(message="The target folder contained %d files, which were ignored." %notfolder)
        if not moreopts5 == 0:
            if self.prompting == 0:
                runnext5 = True
            else:
                runnext5 = messagebox.askyesno(
                    message="Created %d tar archives.\n\nProceed with the next action?" % tarfiles)
        else:
            runnext5 = False
            messagebox.showwarning(message="Created %d tar archives." % tarfiles)
        return runnext5

    def trans_manifest(self, indirectory):
        """
        Generates a manifest of filenames and checksums for a directory of
        Bagged and Tarred objects
        """
        askingdir = path.join(path.basename(path.dirname(indirectory)), path.basename(indirectory))
        indir = ""
        tardest = messagebox.askyesno(message="Create manifest of \'%s-tarred\'?" % askingdir, default='yes')
        if tardest:
            indir = indirectory + "-tarred"
        elif not tardest:
            indir = askdirectory(initialdir=path.dirname(indirectory),
                                 title="In which folder are the objects to be transferred?")
        if not path.exists(indir):
            messagebox.showwarning(message="The directory: \n\'%s\'\n does not exist.\n\nCancelling action." % indir)
            return
        outdir = path.dirname(indir)
        # messagebox.showwarning(message="The transfer manifest will be saved in: \n\'%s\'" %outdir)
        compfile = open(
            path.join(outdir, "Transfer_%s_%s.csv" % (path.basename(indir), time.strftime("%m%d_%H%M%S"))), 'w',
            encoding='utf-8')
        for base, dirs, files in walk(indir):
            for name in files:
                pathname = path.join(base, name)
                if path.basename(pathname) == '.DS_Store':
                    remove(pathname)
                elif not path.basename(pathname) == '.DS_Store':
                    sha3sum = self.sha3hash(pathname)
                    compfile.write("%s, " % name + "%s\n" % sha3sum)
        compfile.close()
        messagebox.showwarning(message="Transfer Manifest Created.")
        return

    def pre_pack(self, packdir):
        """
        Preserves departmental folder structure during Bagging by moving
        object contents into a subdirectory named with the local object ID
        """
        for item in listdir(packdir):
            olditempath = path.join(packdir, item)
            if path.isdir(olditempath):
                newdirpath = path.join(olditempath, path.basename(olditempath))
                temppath = path.join(olditempath, 'temptemptemp')
                shutil.copytree(olditempath, temppath)
                for thing in listdir(olditempath):
                    thingpath = path.join(olditempath, thing)
                    if not thing == 'temptemptemp':
                        if path.isdir(thingpath):
                            shutil.rmtree(thingpath)
                        elif not 'meta' in thing:
                            remove(thingpath)
                rename(temppath, newdirpath)
        return packdir

    def run_procs(self, root, frame2):
        runnext = True
        olditemsdir = self.e1.get()
        meta = frame2.metavar.get()
        regstr = frame2.regisvar.get()
        inv = frame2.invenvar.get()
        bagit = frame2.bagitvar.get()
        tar = frame2.tarvar.get()
        trans = frame2.transvar.get()
        self.prompting = frame2.prompt.get()
        nselect = 0
        for d in [meta, regstr, inv, bagit, tar, trans]:
            if d == 1:
                nselect += 1
        if olditemsdir == "":
            messagebox.showwarning(message="You must first select a folder.")
            return
        if not path.exists(olditemsdir):
            messagebox.showwarning(message="Items folder:\n\'%s\'\nnot found." % olditemsdir)
            return
        if nselect == 0:
            messagebox.showwarning(message="You have not selected any \'Options\'.")
            return
        # PrePack items
        prepack = messagebox.askyesno(title="Pre-Packaging",
                                      message="Is this the first time running UDOF on THESE items?\n(Clicking \'yes\' will \'pre-package\' them.)",
                                      default='no')
        if prepack == False:
            itemsdir = olditemsdir
        else:
            itemsdir = self.pre_pack(olditemsdir)
        # Run CSV meta
        if meta == 1:
            nselect -= 1
            metainput = self.e2.get()
            idcolumn = self.e3.get()
            if metainput == "":
                messagebox.showwarning(message="You must choose a CSV master metadata file.")
                return
            if not path.exists(metainput):
                messagebox.showwarning(message="CSV file:\n\'%s\'\nnot found. Stopping action." % metainput)
                return
            if path.splitext(metainput)[1] == '.csv' and idcolumn == "":
                messagebox.showwarning(message="You must choose the column of ID's in the CSV.")
                return
            runnext = self.create_meta(root, itemsdir, metainput, idcolumn, nselect)
            if runnext == False:
                return
        # Assign UUID's and Register Objects
        if regstr == 1:
            nselect -= 1
            runnext = self.register_obj(itemsdir, nselect)
            if runnext == False:
                return
        # Run Inventory
        if inv == 1:
            nselect -= 1
            runnext = self.run_inventory(itemsdir, nselect)
            if runnext == False:
                return
        # Run BagIt
        if bagit == 1:
            nselect -= 1
            self.run_bagit(itemsdir, nselect)
            if runnext == False:
                return
        # Run Tar
        if tar == 1:
            nselect -= 1
            runnext = self.run_tar(itemsdir, nselect)
            if runnext == False:
                return
        # Make Transfer Manifest
        if trans == 1:
            self.trans_manifest(itemsdir)
        return


def instructions(fontsize):
    new = Toplevel()
    nw = 850
    nh = 600
    nws = new.winfo_screenwidth()  # width of the screen
    nhs = new.winfo_screenheight()  # height of the screen
    nx = (nws / 2) - (nw / 2)
    ny = (nhs / 2) - (nh / 2)
    new.geometry('%dx%d+%d+%d' % (nw, nh, nx, ny))
    new.title('U-Pack Instructions')
    new.configure(bg=vtmaroon, pady=5, padx=5)
    new.grid_propagate(False)
    new.grid_rowconfigure(0, weight=1)
    new.grid_columnconfigure(0, weight=1)
    txt = Text(new, relief='sunken', bd=4, fg='black', bg=vtsmoke)
    txt.config(pady=10, padx=40, font=('Times', fontsize), wrap='word')
    txt.grid(column=0, row=0, sticky='nsew')
    scroller = Scrollbar(new, orient='vertical', command=txt.yview)
    scroller.grid(column=1, row=0, sticky='nsew')
    txt['yscrollcommand'] = scroller.set
    OKa = Button(new, command=new.destroy, text='OK')
    OKa.configure(bg=hokiestone, bd=4, fg='black', font=('Arial', fontsize), highlightbackground=vtmaroon,
                  relief='raised')
    OKa.grid(column=0, row=1, sticky='nsew')
    instructtext = resource_path("UPackInstructions.txt")
    if path.exists(instructtext):
        with open(instructtext) as inst:
            quote = inst.read()
            txt.insert('end', quote)
    else:
        pathstring = str(instructtext)
        messagebox.showwarning(message="Cannot find the file:\n\'%s\'." % pathstring)


def main():
    root = tk.Tk()
    if MY_OS == 'Windows':
        w = 633
        h = 577
    elif MY_OS == 'Linux':
        w = 711
        h = 558
    else:
        w = 709
        h = 562
    ws = root.winfo_screenwidth()
    hs = root.winfo_screenheight()
    x = (ws / 2) - (w / 2)
    y = (hs / 2) - (h / 2)
    root.geometry('%dx%d+%d+%d' % (w, h, x, y))
    root.title('U-Pack Digital Object Formatter')
    root.configure(bg=vtorange, bd=4)
    # Run main app
    app = ObjFormatter(root)
    root.lift()
    root.attributes("-topmost", True)
    root.after_idle(root.attributes, "-topmost", False)
    root.mainloop()


if __name__ == '__main__':
    main()
