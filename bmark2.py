#!/usr/bin/env python

# This is the refactored version for the benchmark script. Once this
# is completely under test coverage, the original benchmark.py gets
# turned into this, then this can be deleted.

# TODO: Why are records over & underclumped? ie. Charles Linder 7475467,
# Nirmala Ramanujam 7570988, Edwin L. Thomas 7799416

# TODO: Investigate "WEIRDNESS" output : Jaro-Winkler exception
# thrown on comparison between  and ROBERT BRUCE
# Underclumping: unique records vs. total records


import sqlite3, sys, csv, datetime;
import argparse
sys.path.append( './lib/' )
sys.path.append("lib")
from fwork import *
from bmconfig import *


# This is what is known as "testable code"
def get_filename_suffix(filename):
    return filename.split(".")[-1].lower()

# More testable code...
def is_csv_file(filename):
    return get_filename_suffix(filename) == "csv"


def print_diagnostics(data, table, header, tList):
   print "Printing diagnostics..."
   print "data: ", data
   print "table: ", table
   print "header: ", header
   print "tList: ", tList


def create_match_tables(c, fBnme, uqB, exCom, exAnd):
    # TODO: Split this query into two functions, test each
    c.executescript("""
        /* EXPAND UNIQUE BASE AND INDICATE ACTIVE MATCHES */
        CREATE TABLE dataM3 AS
        SELECT  uqS, a.*
          FROM (SELECT  uqS AS uqSUB, a.*
              FROM (SELECT  uqB, b.*
                  FROM  (SELECT DISTINCT(uqB) FROM dataM2 WHERE uqB!="") AS a
                INNER JOIN  %s AS b
                    ON  a.uqB=b.%s) AS a
             LEFT JOIN (SELECT %s, uqB, uqS FROM dataM2) AS b
                ON  a.uqB=b.uqB AND %s) AS a
        INNER JOIN (SELECT DISTINCT uqB, uqS FROM dataM2) AS b
            ON  a.%s=b.uqB;

        /* INDICATE INVENTORS WHO DO NOT MATCH */
        CREATE TABLE dataM4 AS
        SELECT  errD(a.ErrUQ, uqB) AS ErrUQ, b.*
          FROM (SELECT uqS, freqUQ(uqB) as ErrUQ FROM dataM3 GROUP BY uqS) AS a
        INNER JOIN  dataM3 AS b
            ON  a.uqS=b.uqS AND b.AppYear <= '2010' /*AND a.uqS not in (83, 85, 93)*/
          ORDER BY  uqS, %s;

        """ % (fBnme, uqB, exCom, exAnd, uqB, exCom))


def handle_fuzzy_dataS(c, exCom, uqB, uqS, fuzzy, fBnme, exAnd):
	# TODO: Remove leading CREATE INDEX as its already been created in the
	# calling function
	# TODO: Split this into 3 functions, no reason to do all this work in
	# one monster query.
        c.executescript("""
        CREATE INDEX IF NOT EXISTS dS_E ON dataS (%s);

        /* RETAIN ONLY JARO>0.9 FUZZY AND EXACT MATCHES */
        CREATE TABLE dataM AS
            SELECT  a.*, %s AS uqB, %s AS uqS, %s AS jaro
              FROM  %s AS a
        INNER JOIN  dataS AS b
            ON  %s
             WHERE  jaro>0.90;

        /* DETERMINE MAXIMUM JARO FOR EACH UQ AND EXACT COMBO */
        CREATE TABLE dataT AS
            SELECT  uqS, %s, MAX(jaro) AS jaro, count(*) as cnt
              FROM  dataM
          GROUP BY  uqS, %s;

        /* RETAIN ONLY MAXIMUM JARO */
        CREATE TABLE dataM2 AS
            SELECT  a.*
              FROM  dataM AS a
        INNER JOIN  dataT AS b
            ON  a.uqS=b.uqS AND a.jaro=b.jaro AND %s;
        """ % (exCom, uqB, uqS, 
               "*".join(["jarow(a.%s, b.%s)" % (x,x) for x in fuzzy]),
               fBnme, exAnd, exCom, exCom, exAnd))

def handle_nonfuzzy_dataS(uqB, uqS, fBnme, exAnd):
    c.executescript("""
	CREATE TABLE dataM2 AS
	    SELECT  *, %s AS uqB, %s AS uqS
	      FROM  %s AS a
	INNER JOIN  dataS AS b
		ON  %s;
	""" % (uqB, uqS, fBnme, exAnd))


def export_csv_results(c, output):
	writer = csv.writer(open(output, "wb"), lineterminator="\n")
	writer.writerows([[x[1] for x in c.execute("PRAGMA TABLE_INFO(dataM4)")]])
	writer.writerows(c.execute("SELECT * FROM dataM4").fetchall())


# TODO: Create functions for handling true and false positives and negatives,
# compute all the relevant statistics using those measures instead of the
# mess of inline computation following the heredoc.
def print_results(c, output, t):
	#print "Printing results ..." + str(datetime.datetime.now())
	rep = [list(x) for x in c.execute("SELECT ErrUQ, uqSUB FROM dataM4")]
	#print "Rep: ", rep
	orig = len([x for x in rep if x[1]!=None])
	errm = sum([int(x[0]) for x in rep if x[0]!=None])
	#print errm
	u = 1.0*errm/orig
	o = 1-(float(orig)/len(rep))
	recall = 1.0 - u
	# overclumping is lumping
	# underclumping is splitting
	print """

	RESULTS ==================

	     Original: {original}
	  New Records: {new}
		Total: {total}

	    Overclump: {overclump} ({o:.2%})
	   Underclump: {underclump} ({u:.2%})
	    Precision: {precision:.2%}
	       Recall: {recall:.2%}
	  File Detail: {filename}
		 Time: {time}
	""".format(original = orig, new = len(rep)-orig, total = len(rep), overclump = len(rep)-orig, o = o,
		   underclump = errm, u = u, recall = recall, precision = recall/(recall+o), filename = output,
		   time = datetime.datetime.now()-t)


def attach_database(c, fileB, tblB, exCom, exAnd):
	# TODO: Replace with call to is_csv_file(fileB)
	if fileB.split(".")[-1].lower()=="csv":
	# TODO: Try to move some of this to a function
	    dataB = uniVert([x for x in csv.reader(open("%s" % fileB, "rb"))])

	    print_diagnostics(dataB, "dataB", True, ["Patent VARCHAR"])
	    #quickSQL(c, data=dataB,  table="dataB", header=True, typeList=["Patent VARCHAR"])
	    quickSQL2(c, data=dataB,  table="dataB", header=True, typeList=["Patent VARCHAR"])

	    c.execute("CREATE INDEX IF NOT EXISTS dB_E ON dataB (%s)" % exCom)
	    c.execute("CREATE INDEX IF NOT EXISTS dB_U ON dataB (%s)" % uqB)
	    fBnme = "dataB"
	# fileB is an SQLite3 database file...
	else:
	    c.execute("ATTACH DATABASE '%s' AS db" % fileB)
	    # fBnme is, apparently a table name. Or maybe a tbl nme...
	    if tblB=="":
		fBnme = "db.%s" % fileB.split(".")[-2].split("/")[-1]
	    else:
		fBnme = "db.%s" % tblB

        return fBnme


def handle_dataS(c, exCom, uqB, uqS, fuzzy, fBnme, exAnd):
	c.execute("CREATE INDEX IF NOT EXISTS dS_E ON dataS (%s);" % (exCom))
	if fuzzy:
	    handle_fuzzy_dataS(c, exCom, uqB, uqS, fuzzy, fBnme, exAnd)
	else:
	    handle_nonfuzzy_dataS(uqB, uqS, fBnme, exAnd)

def print_match_qualifiers(exact, fuzzy, uqS):
	print "Exact: ", exact
	print "Fuzzy: ", fuzzy
	print "uqS: ", uqS


def bmVerify(results, filepath="", outdir = ""):
        """
        Analysis function on disambiguation results, assuming that all benchmark data
        are in the large results dataset.

        Creates analysis detail csv file and prints summary information on
        over- and underclumping statistics.

        Running from the command line (make sure to set correct file paths in file)
        python bmVerify_v3.py "input filepath" "output directory" databases
        example:
        python bmVerify_v3.py /home/ysun/disambig/newcode/all/ /home/ayu/results_v2/ invpatC_NBNA.good.Jan2011 invpatC_NBYA.good.Jan2011 invpatC_YBNA.good.Jan2011

        Running interactively:
        import bmVerify_v3
        bmVerify(['final_r7', 'final_r8'], filepath="/home/ysun/disambig/newcode/all/", outdir = "/home/ayu/results_v2/")

        """

	# TODO: Move these out of this function completely, and into the top
	# part of this file.
	uqB = "Unique_Inventor_ID2"
	tblB = "invpat"
	#fileS = "/home/ron/disambig/BM/DefTruth5.csv"
	#fileS = "/home/doolin/src/patentbenchmarks/DefTruth5.csv"
	#fileS = "/home/doolin/src/patentbenchmarks/berkeley.csv"
	fileS = "/home/doolin/src/patentbenchmarks/pister.csv"
	#fileS = "/home/doolin/src/patentbenchmarks/paulrgray.csv"
	#fileS = "/home/doolin/src/patentbenchmarks/allbritton.csv"
	#fileS = "/home/doolin/src/patentbenchmarks/siddhu.csv"
	#fileS = "/var/share/patentdata/disambiguation/experiments/earth/berkeley/benchmark.csv"

        for result in results:

                fileB = filepath + "{result}.sqlite3".format(result=result)
                output = outdir + "{result}_DT5.csv".format(result=result)

                t=datetime.datetime.now()

                print "Start time: " + str(datetime.datetime.now())

		# TODO: Move freqUQ out of this function if possible.
                class freqUQ:
                    def __init__(self):
                        self.list=[]
                    def step(self, value):
                        self.list.append(value)
                    def finalize(self):
                        return sorted([(self.list.count(x), x) for x in set(self.list)], reverse=True)[0][1]

                #MAKE THIS SO IT CAN ATTACH SQLITE3 FOR BENCHMARK
		# UniqueID,Patent,Lastname,Firstname
		# ,VARCHAR,,
		# ,%08d,,
		# UNIQUE,EXACT,FUZZY,FUZZY
		# 1,5773227,ALLBRITTON,NANCY L
                dataS = uniVert([x for x in csv.reader(open(fileS, "rb"))])
                #print dataS

		# TODO: Refactor into create_column_types()
                #1 = Variables, 2 = Type, 3 = Format (If necessary), 4 = Matching Type
                tList = ["%s %s" % (dataS[0][i], x) for i,x in enumerate(dataS[1]) if  x != ""]
                print "tList: ", tList

		# Slice out rows 1, 2 & 3 from dataS. This is the data which gets
		# put in the database created below, and used for matching.
		# TODO: Refactor into slice_header_out()
                dataS2 = [dataS[0]]
                dataS2.extend(dataS[4:])

                #Format if its necessary --> Basically for Patents..
                for i,x in enumerate(dataS[2]):
                    if x!="":
                        for j in xrange(1,len(dataS2)):
                            if dataS2[j][i].isdigit():
                                dataS2[j][i] = x % int(dataS2[j][i])

                conn = sqlite3.connect(":memory:")
                conn.create_function("jarow", 2, jarow)
                conn.create_function("errD", 2, lambda x,y: (x!=y) and 1 or None)
                conn.create_aggregate("freqUQ", 1, freqUQ)
                c = conn.cursor()

                #FIGURE OUT WHICH ONES HAVE EXACT/FUZZY
                exact = [dataS[0][i] for i,x in enumerate(dataS[3]) if x.upper()[0]=="E"]
                fuzzy = [dataS[0][i] for i,x in enumerate(dataS[3]) if x.upper()[0]=="F"]
                uqS =   [dataS[0][i] for i,x in enumerate(dataS[3]) if x.upper()[0]=="U"][0]
                print_match_qualifiers(exact, fuzzy, uqS)

                #CREATE INDEX, MERGE DATA BASED ON EXACTS
                print "Creating indices... " + str(datetime.datetime.now())

                exAnd = " AND ".join(["a.%s=b.%s" % (x, x) for x in exact])
		print "exAnd: ", exAnd
                exCom = ", ".join(exact)
                print "exCom: ", exCom

                fBnme = attach_database(c, fileB, tblB, exCom, exAnd)

                print_diagnostics(dataS2, "dataS", True, tList)
                #quickSQL(c, data=dataS2, table="dataS", header=True, typeList=tList)
                quickSQL2(c, data=dataS2, table="dataS", header=True, typeList=tList)

		handle_dataS(c, exCom, uqB, uqS, fuzzy, fBnme, exAnd)

                create_match_tables(c, fBnme, uqB, exCom, exAnd)

                print "Indices Done ... " + str(datetime.datetime.now())

		export_csv_results(c, output)
		print_results(c, output, t)
                c.close()
                conn.close()


if __name__ == "__main__":
    import sys
    if(sys.argv[1] == 'help' or sys.argv[1] == '?'):
        print bmVerify.__doc__

    else:
            bmVerify(sys.argv[3:], sys.argv[1], sys.argv[2])
