#!/usr/bin/evn python
# -*- coding: utf-8 -*-
import os
import sys
import re
import urllib
import time
import tempfile

try:
	from pysqlite2 import dbapi2 as sqlite3
except ImportError:
	import sqlite3

try:
	from PySide.QtCore import *
	from PySide.QtGui import *
except ImportError:
	from PyQt4.QtCore import *
	from PyQt4.QtGui import *

class KEGGMainWindow(QMainWindow):
	def __init__(self):
		super(KEGGMainWindow, self).__init__()
		self.statusbar = self.statusBar().showMessage('Go')
		self.toolbar = self.addToolBar('exit')
		self.resize(1000, 700)
		self.setWindowTitle('KEGGAnalyzer')
		self.show()
		
		self.tree = QTreeWidget()
		self.tree.setSelectionMode(QAbstractItemView.SingleSelection)
		self.tree.setColumnCount(5)
		self.tree.setHeaderLabels(["Name", "Sequences","Pathway ko", "Mapped gene", "Known gene", "Mapped percentage"])
		self.tree.itemDoubleClicked.connect(self.treeItemClicked)
		self.tree.setSortingEnabled(True)
		self.view = QTreeView()
		self.viewModel = QStandardItemModel(self)
		self.view.setModel(self.viewModel)
		self.view.setRootIsDecorated(0)
		self.view.setSortingEnabled(1)
		
		splitter = QSplitter(self)
		splitter.addWidget(self.tree)
		splitter.addWidget(self.view)
		splitter.setOrientation(Qt.Horizontal)
		splitter.setStretchFactor(0, 5)
		splitter.setStretchFactor(1, 4)
		splitter.setHandleWidth(3)
		self.setCentralWidget(splitter)

		self.createActions()
		self.createMenus()
		self.createToolButtons()
		self.createSqliteDb()
		self.createTempDir()

	def createTempDir(self):
		self.tempDir = os.path.join(tempfile.gettempdir(), "KEGG")
		if not os.path.exists(self.tempDir):
			os.mkdir(self.tempDir)

	def createSqliteDb(self):
		self.db = sqlite3.connect(":memory:")
		self.db.row_factory = sqlite3.Row
		sql = '''
			create table kegg (
				cat text,
				subCat text,
				pathway text,
				pathId text,
				seq text,
				ko text,
				name text,
				description text,
				enzyme text
			);
		'''
		self.db.execute(sql)

	def createActions(self):
		self.openAct = QAction(QIcon("img/file-add.png"), self.tr("&Open keg file"), self,
			shortcut = QKeySequence.Open,
			statusTip = self.tr("Open a new keg file"),
			triggered = self.openKegFile
		)
		self.closeAct = QAction(self.tr("&Close"), self,
			shortcut = QKeySequence.Close,
			statusTip = self.tr("Close keg file"),
			triggered = self.doCloseKeg
		)
		self.saveAct = QAction(QIcon("img/save.png"), self.tr("&Save"), self,
			shortcut = QKeySequence.Save,
			statusTip = self.tr("Save file"),
			triggered = self.doSave
		)
		self.saveAsAct = QAction(QIcon("img/save-as.png"), self.tr("&Save as"), self,
			shortcut = QKeySequence.SaveAs,
			statusTip = self.tr("Save file as format"),
			triggered = self.doSaveAs
		)
		self.exportAct = QAction(self.tr("&Export results"), self,
			statusTip = "Export results",
			triggered = self.doExportResult	
		)
		self.exitAct = QAction(QIcon("img/quit.png"), self.tr("&Quit"), self,
			shortcut =QKeySequence.Quit,
			statusTip = self.tr("Quit"),
			triggered = self.doQuit
		)
		self.levelOneAct = QAction(QIcon("img/1.png"), self.tr("&Level 1"), self,
			statusTip = self.tr("Show level 1"),
			triggered = self.showLevelOne
		)
		self.levelTwoAct = QAction(QIcon("img/2.png"), self.tr("&Level 2"), self,
			statusTip = self.tr("Show level 2"),
			triggered = self.showLevelTwo
		)
		self.levelThreeAct = QAction(QIcon("img/3.png"), self.tr("&Level 3"), self,
			statusTip = self.tr("Show level 3"),
			triggered = self.showLevelThree
		)

		self.knownGeneAct = QAction(self.tr("&Download pathway information"), self,
			statusTip = self.tr("Get pathway known genes"),
			triggered = self.downloadPathwayInfo
		)
		self.pathwayImageAct = QAction(self.tr("&Display pathway image"), self,
			statusTip = self.tr("Download pathway image and display"),
			triggered = self.getPathwayImage
		)

	def createToolButtons(self):
		self.toolbar.addAction(self.openAct)
		self.toolbar.addAction(self.levelOneAct)
		self.toolbar.addAction(self.levelTwoAct)
		self.toolbar.addAction(self.levelThreeAct)

	def createMenus(self):
		self.menubar = self.menuBar()
		self.fileMenu = self.menubar.addMenu("&File")
		self.fileMenu.addAction(self.openAct)
		self.fileMenu.addAction(self.closeAct)
		self.fileMenu.addAction(self.saveAct)
		self.fileMenu.addAction(self.saveAsAct)
		self.fileMenu.addSeparator()
		self.fileMenu.addAction(self.exportAct)
		self.fileMenu.addSeparator()
		self.fileMenu.addAction(self.exitAct)
		self.editMenu = self.menubar.addMenu("&Edit")
		self.viewMenu = self.menubar.addMenu("&View")
		self.viewMenu.addAction(self.levelOneAct)
		self.viewMenu.addAction(self.levelTwoAct)
		self.viewMenu.addAction(self.levelThreeAct)
		self.viewMenu.addSeparator()
		self.toolMenu = self.menubar.addMenu("&Tool")
		self.toolMenu.addAction(self.knownGeneAct)
		self.toolMenu.addAction(self.pathwayImageAct)
		self.helpMenu = self.menubar.addMenu("&Help")

	def showLevels(self):
		self.tree.clear()
		cursor = self.db.cursor()
		for cat in cursor.execute("SELECT cat,count(1) FROM kegg GROUP BY cat"):
			QTreeWidgetItem(self.tree, map(str, cat))

		for sub in cursor.execute("SELECT cat,subCat,count(1) FROM kegg GROUP BY subCat"):
			item = self.tree.findItems(str(sub[0]), Qt.MatchExactly | Qt.MatchRecursive)[0]
			QTreeWidgetItem(item, [sub[1], str(sub[2])])

		for pathway in cursor.execute("SELECT subCat,pathway,pathId,count(distinct(ko)),count(distinct(seq)) FROM kegg GROUP BY pathway"):
			item = self.tree.findItems(str(pathway[0]), Qt.MatchExactly | Qt.MatchRecursive)[0]
			QTreeWidgetItem(item, [pathway[1], str(pathway[4]), pathway[2], str(pathway[3])])

		for i in range(5):
			self.tree.resizeColumnToContents(i)
		
		cursor.close()

	def treeItemClicked(self, item):
		if item.childCount() > 0: return
		pathway = item.text(0)
		subCategory = item.parent().text(0)
		category = item.parent().parent().text(0)
		self.viewModel.clear()
		self.viewModel.setColumnCount(6)
		self.viewModel.setHorizontalHeaderLabels(['Orthology', 'Name', 'Description', 'Enzyme', 'Sequences','Sequences name'])
		kos = {}
		for item in self.db.execute("SELECT seq,ko,name,description,enzyme FROM kegg WHERE pathway=? AND cat=? AND subCat=?", (pathway, category, subCategory)):
			if item[1] in kos:
				kos[item[1]][0].append(item[0])
			else:
				kos[item[1]] = [[item[0]], item[2], item[3], item[4]]		
		
		for ko in kos:
			row = [ko, kos[ko][1], kos[ko][2], kos[ko][3], str(len(kos[ko][0])), ", ".join(kos[ko][0])]
			row = map(QStandardItem, row)
			self.viewModel.appendRow(row)

		for i in range(6):
			self.view.resizeColumnToContents(i)	

	def openKegFile(self):
		kegs = QFileDialog.getOpenFileNames(self, "Open File...", "",
			"Keg Files (*.keg);;All Files (*)")[0]
		
		if kegs == '': return

		for keg in kegs:
			self.paraseKeg(keg)
		self.showLevels()

	def paraseKeg(self, keg):
		self.db.execute("DELETE FROM kegg")
		sql = "INSERT INTO kegg VALUES (%s)" % ",".join(["?"]*9)
		with open(keg) as fh:
			for item in KEGGParaser(fh):
				self.db.execute(sql, item)

	def downloadPathwayInfo(self):
		cursor = self.db.cursor()
		cursor.execute("SELECT DISTINCT(pathId) AS ko,pathway FROM kegg")
		kos = cursor.fetchall()
		cursor.close()
		dialog = QProgressDialog("Download and parser pathway information...", "Cancel", 0, len(kos), self)
		dialog.show()
		dialog.setMinimumDuration(0)
		dialog.setWindowTitle("Download")
		dialog.setWindowModality(Qt.WindowModal)
		dialog.setValue(0)

		for progress, ko in enumerate(kos):
			QCoreApplication.instance().processEvents()
			if dialog.wasCanceled(): break
			dialog.setLabelText("Download and parse pathway:\n\t%s" % ko['pathway'])
			temp = os.path.join(self.tempDir, ko['ko'])
			if not os.path.exists(temp):
				f = urllib.urlopen("http://rest.kegg.jp/get/ko%s" % ko['ko'])
				if f.getcode() == 200:
					with open(temp, "w") as op:
						op.write(f.read())
			with open(temp) as fp:
				for line in fp:
					if line.split()[0] == 'ORTHOLOGY': break
				count = 1
				for line in fp:
					if line.split()[0] == 'REFERENCE': break
					count += 1
				item = self.tree.findItems(str(ko['ko']), Qt.MatchExactly | Qt.MatchRecursive, 2)[0]
				mapped = float(item.text(3))
				percent = round(mapped/count*100, 2)
				item.setText(4, str(count))
				item.setText(5, str(percent))
				dialog.setValue(progress+1)

	def getPathwayImage(self):
		item = self.tree.currentItem()
		if item is None: return
		print item.text(0)


	def doCloseKeg(self):
		self.db.execute("DELETE FROM kegg")
		self.tree.clear()

	def doSave(self):
		pass

	def doSaveAs(self):
		pass

	def doExportResult(self):
		out = QFileDialog.getSaveFileName(self, "Save File...", "",
			"All Files (*)")[0]
		
		if out == '': return
		fp = open(out, "w")
		it = QTreeWidgetItemIterator(self.tree)
		while it.value():
			item = it.value()
			parent = item.parent()
			child = item.childCount()
			if parent and child:
				head = '  '
			elif child == 0:
				head = '    '
			else:
				head = ''
			
			fp.write("%s%s\n" % (head, "\t".join([item.text(i) for i in range(6)])))
			it += 1
		fp.close()

	def doQuit(self):
		self.close()

	#view menu actions
	def showLevelOne(self):
		for i in range(self.tree.topLevelItemCount()):
			parent = self.tree.topLevelItem(i)
			self.tree.collapseItem(parent)
			for j in range(parent.childCount()):
				child = parent.child(j)
				if self.tree.isItemExpanded(child):
					self.tree.collapseItem(child)

	def showLevelTwo(self):
		for i in range(self.tree.topLevelItemCount()):
			parent = self.tree.topLevelItem(i)
			self.tree.expandItem(parent)
			for j in range(parent.childCount()):
				child = parent.child(j)
				if self.tree.isItemExpanded(child):
					self.tree.collapseItem(child)

	def showLevelThree(self):
		for i in range(self.tree.topLevelItemCount()):
			parent = self.tree.topLevelItem(i)
			self.tree.expandItem(parent)
			for j in range(parent.childCount()):
				child = parent.child(j)
				if not self.tree.isItemExpanded(child):
					self.tree.expandItem(child)

class xdict(dict):
	def __getitem__(self, name):
		try:
			return self[name]
		except:
			raise AttributeError(name)
	def __setitem__(self, name, value):
		self[name] = value

def KEGGParaser(fh):
	for line in fh:
		line = line.strip()
		if line.startswith(('+','#','!')):
			continue
		if line[0] == 'A':
			m = re.search("<b>([^<>]+)</b>", line)
			category = m.group(1)
		elif line[0] == 'B' and len(line) == 1:
			continue
		elif line[0] == 'B' and len(line) > 1:
			m = re.search("<b>([^<>]+)</b>", line)
			subCategory = m.group(1)
		elif line[0] == 'C':
			m = re.search("^C\s+(\d+)([^\[]+)", line)
			pathwayId = m.group(1)
			pathway = m.group(2).strip()
		elif line[0] == 'D':
			cols = line[1:].split(';')
			ko, name = cols[1].strip().split('  ')
			gene = cols[0].strip()
			description = cols[2].split("[EC:")[0].strip()
			try:
				enzyme = cols[2].split("[EC:")[1].strip("]")
			except:
				enzyme = None
			yield (category, subCategory, pathway, pathwayId, gene, ko, name, description, enzyme)

if __name__ == '__main__':
	app = QApplication(sys.argv)
	mw = KEGGMainWindow()
	sys.exit(app.exec_())