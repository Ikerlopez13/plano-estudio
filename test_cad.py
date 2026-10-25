import unittest, io, math
import cad
import pymupdf

class CadTests(unittest.TestCase):
    def test_editable_roundtrip(self):
        doc=cad.apply(cad.fresh(),cad.example())
        reopened=cad.loads(cad.dumps(doc))
        self.assertFalse(reopened.audit().has_errors)
        self.assertEqual(reopened.units,4)
        dims=list(reopened.modelspace().query('DIMENSION'))
        self.assertEqual(len(dims),2)
        labels=[e.dxf.text for dim in dims for e in reopened.blocks.get(dim.dxf.geometry) if e.dxftype()=='MTEXT']
        self.assertEqual(sorted(labels),['4000','6000'])
        self.assertEqual(sorted(round(e.get_measurement()) for e in dims),[4000,6000])
        self.assertEqual(len(reopened.modelspace().query('ARC')),1)
    def test_invalid_proposal_atomic(self):
        doc=cad.fresh()
        with self.assertRaises(ValueError):
            cad.apply(doc,{'operations':[{'type':'rect','origin':[0,0],'width':100,'height':100},{'type':'wall','start':[0,0],'end':[100,0],'thickness':10,'openings':[{'offset':90,'width':30,'kind':'door'}]}]})
        self.assertEqual(len(doc.modelspace()),0)
    def test_move_delete_preserve_original(self):
        d=cad.apply(cad.fresh(),{'operations':[{'type':'line','start':[0,0],'end':[100,0]}]})
        h=next(iter(d.modelspace())).dxf.handle
        moved=cad.apply(d,{'operations':[{'type':'move','handles':[h],'delta':[300,500]}]})
        self.assertEqual(tuple(moved.entitydb[h].dxf.start),(300,500,0))
        self.assertEqual(tuple(d.entitydb[h].dxf.start),(0,0,0))
        deleted=cad.apply(moved,{'operations':[{'type':'delete','handles':[h]}]})
        self.assertEqual(len(deleted.modelspace()),0)
    def test_scale_and_pdf(self):
        doc=cad.sheet(cad.apply(cad.fresh(),cad.example()),scale=50)
        vp=[v for v in doc.layouts.get('PE_Entrega').query('VIEWPORT') if v.dxf.status==2][0]
        self.assertAlmostEqual(vp.dxf.view_height/vp.dxf.height,50)
        pdf=pymupdf.open(stream=cad.render(doc,True,True),filetype='pdf')
        self.assertEqual(len(pdf),1)
        self.assertAlmostEqual(pdf[0].rect.width,420*72/25.4,places=2)
        self.assertAlmostEqual(pdf[0].rect.height,297*72/25.4,places=2)
        self.assertGreater(len(pdf[0].get_drawings()),20)
    def test_sheet_overflow_rejected(self):
        with self.assertRaises(ValueError): cad.sheet(cad.apply(cad.fresh(),cad.example()),paper='A4',scale=20)
    def test_door_gap(self):
        d=cad.apply(cad.fresh(),{'operations':[{'type':'wall','start':[0,0],'end':[4000,0],'thickness':150,'openings':[{'offset':1000,'width':900,'kind':'door'}]}]})
        walls=list(d.modelspace().query('LWPOLYLINE'))
        self.assertEqual(len(walls),2)
        self.assertEqual(max(p[0] for p in walls[0].get_points()),1000)
        self.assertEqual(min(p[0] for p in walls[1].get_points()),1900)

if __name__=='__main__': unittest.main()
