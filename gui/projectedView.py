#===============================================================================
# Copyright (C) 2010 Diego Duclos
#
# This file is part of pyfa.
#
# pyfa is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# pyfa is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with pyfa.  If not, see <http://www.gnu.org/licenses/>.
#===============================================================================

import wx
import gui.display as d
import gui.globalEvents as GE
import service
import gui.droneView
from gui.builtinViewColumns.state import State
from gui.contextMenu import ContextMenu
import eos.types


class DummyItem:
    def __init__(self, txt):
        self.name = txt
        self.icon = None

class DummyEntry:
    def __init__(self, txt):
        self.item = DummyItem(txt)

class ProjectedViewDrop(wx.PyDropTarget):
   def __init__(self, dropFn):
       wx.PyDropTarget.__init__(self)
       self.dropFn = dropFn
       # this is really transferring an EVE itemID
       self.dropData = wx.PyTextDataObject()
       self.SetDataObject(self.dropData)

   def OnData(self, x, y, t):
       if self.GetData():
           data = self.dropData.GetText().split(':')
           self.dropFn(x, y, data)
       return t

class ProjectedView(d.Display):
    DEFAULT_COLS = ["State",
                    "Ammo Icon",
                    "Base Icon",
                    "Base Name",
                    "Ammo"]

    def __init__(self, parent):
        d.Display.__init__(self, parent, style = wx.LC_SINGLE_SEL | wx.BORDER_NONE)

        self.lastFitId = None

        self.mainFrame.Bind(GE.FIT_CHANGED, self.fitChanged)
        self.Bind(wx.EVT_LEFT_DOWN, self.click)
        self.Bind(wx.EVT_RIGHT_DOWN, self.click)
        self.Bind(wx.EVT_LEFT_DCLICK, self.remove)
        self.Bind(wx.EVT_KEY_UP, self.kbEvent)

        self.droneView = gui.droneView.DroneView

        if "__WXGTK__" in  wx.PlatformInfo:
            self.Bind(wx.EVT_RIGHT_UP, self.scheduleMenu)
        else:
            self.Bind(wx.EVT_RIGHT_DOWN, self.scheduleMenu)

        self.Bind(wx.EVT_LIST_BEGIN_DRAG, self.startDrag)
        self.SetDropTarget(ProjectedViewDrop(self.handleListDrag))

    def handleListDrag(self, x, y, data):
        '''
        Handles dragging of items from various pyfa displays which support it

        data is list with two indices:
            data[0] is hard-coded str of originating source
            data[1] is typeID or index of data we want to manipulate
        '''

        if data[0] == "projected":
            # if source is coming from projected, we are trying to combine drones.
            self.mergeDrones(x, y, int(data[1]))
        elif data[0] == "market":
            sFit = service.Fit.getInstance()
            fitID = self.mainFrame.getActiveFit()
            sFit.project(fitID, int(data[1]))
            wx.PostEvent(self.mainFrame, GE.FitChanged(fitID=self.mainFrame.getActiveFit()))

    def kbEvent(self,event):
        keycode = event.GetKeyCode()
        if keycode == wx.WXK_DELETE or keycode == wx.WXK_NUMPAD_DELETE:
            fitID = self.mainFrame.getActiveFit()
            sFit = service.Fit.getInstance()
            row = self.GetFirstSelected()
            if row != -1:
                sFit.removeProjected(fitID, self.get(row))
                wx.PostEvent(self.mainFrame, GE.FitChanged(fitID=fitID))

    def handleDrag(self, type, fitID):
        #Those are drags coming from pyfa sources, NOT builtin wx drags
        if type == "fit":
            activeFit = self.mainFrame.getActiveFit()
            if activeFit:
                sFit = service.Fit.getInstance()
                draggedFit = sFit.getFit(fitID)
                sFit.project(activeFit, draggedFit)
                wx.PostEvent(self.mainFrame, GE.FitChanged(fitID=activeFit))

    def startDrag(self, event):
        row = event.GetIndex()
        if row != -1 and isinstance(self.get(row), eos.types.Drone):
            data = wx.PyTextDataObject()
            data.SetText("projected:"+str(self.GetItemData(row)))

            dropSource = wx.DropSource(self)
            dropSource.SetData(data)
            dropSource.DoDragDrop()

    def mergeDrones(self, x, y, itemID):
        srcRow = self.FindItemData(-1,itemID)
        dstRow, _ = self.HitTest((x, y))
        if srcRow != -1 and dstRow != -1:
            self._merge(srcRow, dstRow)

    def _merge(self, src, dst):
        dstDrone = self.get(dst)
        if isinstance(dstDrone, eos.types.Drone):
            sFit = service.Fit.getInstance()
            fitID = self.mainFrame.getActiveFit()
            if sFit.mergeDrones(fitID, self.get(src), dstDrone, True):
                wx.PostEvent(self.mainFrame, GE.FitChanged(fitID=fitID))


    def moduleSort(self, module):
        return module.item.name

    def fighterSort(self, fighter):
        return fighter.item.name

    def droneSort(self, drone):
        item = drone.item
        if item.marketGroup is None:
            item = item.metaGroup.parent

        return (self.droneView.DRONE_ORDER.index(item.marketGroup.name),
                drone.item.name)

    def fitSort(self, fit):
        return fit.name

    def fitChanged(self, event):
        #Clear list and get out if current fitId is None
        if event.fitID is None and self.lastFitId is not None:
            self.DeleteAllItems()
            self.lastFitId = None
            event.Skip()
            return

        sFit = service.Fit.getInstance()
        fit = sFit.getFit(event.fitID)
        stuff = []
        if fit is not None:
            self.modules = fit.projectedModules[:]
            self.drones = fit.projectedDrones[:]
            self.fighters = fit.projectedFighters[:]
            self.fits = fit.projectedFits[:]

            self.modules.sort(key=self.moduleSort)
            self.drones.sort(key=self.droneSort)
            self.fighters.sort(key=self.fighterSort)
            self.fits.sort(key=self.fitSort)

            stuff.extend(self.modules)
            stuff.extend(self.drones)
            stuff.extend(self.fighters)
            stuff.extend(self.fits)

        if event.fitID != self.lastFitId:
            self.lastFitId = event.fitID

            item = self.GetNextItem(-1, wx.LIST_NEXT_ALL, wx.LIST_STATE_DONTCARE)

            if item != -1:
                self.EnsureVisible(item)

            self.deselectItems()

        if stuff == []:
            stuff = [DummyEntry("Drag an item or fit, or use right-click menu for system effects")]

        self.update(stuff)

    def get(self, row):
        numMods = len(self.modules)
        numDrones = len(self.drones)
        numFighters = len(self.fighters)
        numFits = len(self.fits)

        if (numMods + numDrones + numFighters + numFits) == 0:
            return None

        if row < numMods:
            stuff = self.modules[row]
        elif row - numMods < numDrones:
            stuff = self.drones[row - numMods]
        elif row - numMods - numDrones < numFighters:
            stuff = self.fighters[row - numMods - numDrones]
        else:
            stuff = self.fits[row - numMods - numDrones - numFighters]

        return stuff

    def click(self, event):
        event.Skip()
        row, _ = self.HitTest(event.Position)
        if row != -1:
            item = self.get(row)
            col = self.getColumn(event.Position)
            if col == self.getColIndex(State):
                fitID = self.mainFrame.getActiveFit()
                sFit = service.Fit.getInstance()
                sFit.toggleProjected(fitID, item, "right" if event.Button == 3 else "left")
                wx.PostEvent(self.mainFrame, GE.FitChanged(fitID=fitID))

    def scheduleMenu(self, event):
        event.Skip()
        if self.getColumn(event.Position) != self.getColIndex(State):
            wx.CallAfter(self.spawnMenu)

    def spawnMenu(self):
        sel = self.GetFirstSelected()
        menu = None
        if sel != -1:
            item = self.get(sel)
            sMkt = service.Market.getInstance()
            if isinstance(item, eos.types.Drone):
                srcContext = "projectedDrone"
                itemContext = sMkt.getCategoryByItem(item.item).name
                context = ((srcContext, itemContext),)
            elif isinstance(item, eos.types.Fighter):
                srcContext = "projectedFighter"
                itemContext = sMkt.getCategoryByItem(item.item).name
                context = ((srcContext, itemContext),)
            elif isinstance(item, eos.types.Module):
                modSrcContext = "projectedModule"
                modItemContext = sMkt.getCategoryByItem(item.item).name
                modFullContext = (modSrcContext, modItemContext)
                if item.charge is not None:
                    chgSrcContext = "projectedCharge"
                    chgItemContext = sMkt.getCategoryByItem(item.charge).name
                    chgFullContext = (chgSrcContext, chgItemContext)
                    context = (modFullContext, chgFullContext)
                else:
                    context = (modFullContext,)
            else:
                fitSrcContext = "projectedFit"
                fitItemContext = item.name
                context = ((fitSrcContext,fitItemContext),)
            context = context + (("projected",),)
            menu = ContextMenu.getMenu((item,), *context)
        elif sel == -1:
            fitID = self.mainFrame.getActiveFit()
            if fitID is None:
                return
            context = (("projected",),)
            menu = ContextMenu.getMenu([], *context)
        if menu is not None:
            self.PopupMenu(menu)

    def remove(self, event):
        row, _ = self.HitTest(event.Position)
        if row != -1:
            col = self.getColumn(event.Position)
            if col != self.getColIndex(State):
                fitID = self.mainFrame.getActiveFit()
                sFit = service.Fit.getInstance()
                sFit.removeProjected(fitID, self.get(row))
                wx.PostEvent(self.mainFrame, GE.FitChanged(fitID=fitID))
