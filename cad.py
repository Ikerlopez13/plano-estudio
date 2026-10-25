"""Motor CAD local. Todas las coordenadas de operaciones están en milímetros."""
import io, math, json, copy
from collections import Counter
import ezdxf
from ezdxf import bbox
from ezdxf.math import Matrix44
from ezdxf.addons.drawing import Frontend, RenderContext, layout, svg, pymupdf, config

LAYERS = {'MUROS': (7, 35), 'PUERTAS': (3, 18), 'VENTANAS': (4, 18), 'MOBILIARIO': (8, 18), 'COTAS': (1, 13), 'TEXTOS': (7, 18), 'LAMINA': (7, 18), 'VIEWPORTS': (8, 0)}

def fresh():
    d = ezdxf.new('R2010', setup=True)
    d.units = 4
    d.header['$MEASUREMENT'] = 1
    d.header['$LUNITS'] = 2
    d.header['$LUPREC'] = 0
    layers(d)
    return d

def layers(d):
    for name, (color, weight) in LAYERS.items():
        if name not in d.layers:
            d.layers.new(name, dxfattribs={'color': color, 'lineweight': weight})
    d.layers.get('VIEWPORTS').dxf.plot = 0

def dumps(d):
    out = io.StringIO(); d.write(out); return out.getvalue()

def loads(s):
    return ezdxf.read(io.StringIO(s))

def extent(d):
    b = bbox.extents(d.modelspace(), fast=True)
    if not b.has_data: return (0, 0, 1000, 1000)
    return (b.extmin.x, b.extmin.y, b.extmax.x, b.extmax.y)

def summary(d):
    entities = []
    for e in d.modelspace():
        row = {'handle': e.dxf.handle, 'type': e.dxftype(), 'layer': e.dxf.layer}
        for k in ('start', 'end', 'insert', 'center', 'radius', 'text'):
            if e.dxf.hasattr(k):
                v = e.dxf.get(k)
                row[k] = list(v) if hasattr(v, 'x') else v
        if e.dxftype() == 'LWPOLYLINE': row['points'] = [list(p[:2]) for p in e.get_points()]
        entities.append(row)
    return {'units': 'mm', 'count': len(entities), 'bounds': extent(d), 'layers': dict(Counter(e.dxf.layer for e in d.modelspace())), 'entities': entities[:2000], 'truncated': len(entities)>2000}

def num(v):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or abs(v)>1e7:
        raise ValueError('Coordenada no válida o fuera del límite de 10 km.')
    return float(v)

def point(v):
    if not isinstance(v, list) or len(v)!=2: raise ValueError('Un punto debe contener [x, y].')
    return tuple(num(x) for x in v)

def positive(v):
    v=num(v)
    if v<=0: raise ValueError('Las dimensiones deben ser positivas.')
    return v

def attrs(d, op, default):
    name=op.get('layer', default)
    if not isinstance(name,str) or not name or len(name)>80 or any(c in name for c in '<>/\\":;?*|=\n\r'):
        raise ValueError('Nombre de capa no válido.')
    if name not in d.layers: d.layers.new(name)
    return {'layer':name}

def rect(m, x,y,w,h,a):
    return m.add_lwpolyline([(x,y),(x+w,y),(x+w,y+h),(x,y+h)], close=True, dxfattribs=a)

def text(m, s, p, h, a):
    s=str(s)
    if len(s)>160 or '\n' in s or '\r' in s: raise ValueError('Texto demasiado largo o multilínea.')
    return m.add_text(s, dxfattribs={**a,'height':h,'insert':p})

def wall(m, op, a):
    start=point(op['start']); end=point(op['end']); t=positive(op['thickness'])
    dx,dy=end[0]-start[0],end[1]-start[1]; length=math.hypot(dx,dy)
    if length<1: raise ValueError('Muro demasiado corto.')
    ux,uy=dx/length,dy/length; nx,ny=-uy,ux
    def p(s,n=0): return (start[0]+ux*s+nx*n,start[1]+uy*s+ny*n)
    openings=sorted(op.get('openings',[]),key=lambda o:o['offset'])
    cursor=0
    for o in openings + [{'offset':length,'width':0,'kind':'end'}]:
        off=num(o['offset']); width=num(o['width'])
        if off<cursor or off<0 or width<0 or off+width>length: raise ValueError('Huecos solapados o fuera del muro.')
        if off>cursor: m.add_lwpolyline([p(cursor,-t/2),p(off,-t/2),p(off,t/2),p(cursor,t/2)],close=True,dxfattribs=a)
        if o['kind']=='door':
            if width<=0: raise ValueError('Puerta sin anchura.')
            da={'layer':'PUERTAS'}
            m.add_line(p(off),p(off,width),dxfattribs=da)
            angle=math.degrees(math.atan2(uy,ux))
            m.add_arc(p(off),width,angle,angle+90,dxfattribs=da)
        elif o['kind']=='window':
            for n in (-t/4,t/4): m.add_line(p(off,n),p(off+width,n),dxfattribs={'layer':'VENTANAS'})
        elif o['kind'] not in ('end','gap'): raise ValueError('Tipo de hueco desconocido.')
        cursor=off+width

def apply(d, package):
    if not isinstance(package,dict) or not isinstance(package.get('operations'),list): raise ValueError('Se necesita un objeto con una lista operations.')
    if len(package['operations'])>500: raise ValueError('Máximo 500 operaciones por cambio.')
    out=loads(dumps(d)); layers(out); m=out.modelspace()
    for op in package['operations']:
        kind=op.get('type')
        if kind=='wall': wall(m,op,attrs(out,op,'MUROS'))
        elif kind in ('line','polyline','rect','circle','arc'):
            a=attrs(out,op,'MOBILIARIO')
            if kind=='line': m.add_line(point(op['start']),point(op['end']),dxfattribs=a)
            elif kind=='polyline':
                pts=op['points']
                if not 2<=len(pts)<=2000: raise ValueError('Polilínea: entre 2 y 2000 puntos.')
                m.add_lwpolyline([point(p) for p in pts],close=bool(op.get('closed',False)),dxfattribs=a)
            elif kind=='rect': rect(m,*point(op['origin']),positive(op['width']),positive(op['height']),a)
            elif kind=='circle': m.add_circle(point(op['center']),positive(op['radius']),dxfattribs=a)
            else: m.add_arc(point(op['center']),positive(op['radius']),num(op['start_angle']),num(op['end_angle']),dxfattribs=a)
        elif kind=='text': text(m,op['text'],point(op['at']),positive(op.get('height',120)),attrs(out,op,'TEXTOS'))
        elif kind=='dimension':
            p1,p2=point(op['p1']),point(op['p2'])
            if p1==p2: raise ValueError('Cota con extremos iguales.')
            m.add_aligned_dim(p1,p2,num(op.get('distance',400)),dxfattribs=attrs(out,op,'COTAS'),override={'dimtxt':100,'dimasz':80,'dimgap':40,'dimexo':40,'dimexe':80,'dimdec':0,'dimlfac':1,'dimscale':1}).render()
        elif kind in ('move','delete'):
            handles=op.get('handles',[])
            if not handles or len(handles)>2000: raise ValueError('Selecciona entidades por sus handles.')
            selected=[]
            for handle in handles:
                e=out.entitydb.get(str(handle))
                if e is None or e not in m: raise ValueError('Entidad inexistente o fuera del espacio modelo: '+str(handle))
                selected.append(e)
            if kind=='delete':
                for e in selected: m.delete_entity(e)
            else:
                dx,dy=point(op['delta'])
                for e in selected: e.transform(Matrix44.translate(dx,dy,0))
        else: raise ValueError('Operación no admitida: '+str(kind))
    if len(m)>30000: raise ValueError('El proyecto supera 30.000 entidades.')
    audit=out.audit()
    if audit.has_errors: raise ValueError('El resultado no ha superado la auditoría DXF.')
    return out

def sheet(d, paper='A3', scale=50, title='Plano de interiores'):
    if paper not in ('A4','A3'): raise ValueError('Selecciona A4 o A3.')
    scale=positive(scale)
    if scale not in (20,25,50,75,100,200): raise ValueError('Escala no admitida.')
    W,H=(420,297) if paper=='A3' else (297,210)
    x0,y0,x1,y1=extent(d); vw,vh=W-30,H-65
    if (x1-x0)/scale>vw or (y1-y0)/scale>vh:
        raise ValueError('El plano no cabe a esa escala. Elige una escala menor (por ejemplo 1:100) o A3.')
    out=loads(dumps(d)); layers(out)
    if 'PE_Entrega' in out.layouts: out.layouts.delete('PE_Entrega')
    p=out.layouts.new('PE_Entrega'); p.page_setup(size=(W,H),margins=(0,0,0,0),units='mm')
    a={'layer':'LAMINA'}
    rect(p,10,10,W-20,H-20,a)
    p.add_line((10,35),(W-10,35),dxfattribs=a)
    text(p,title[:90],(16,23),4,a)
    text(p,f'{paper}  |  ESCALA 1:{int(scale)}  |  MODELO EN mm',(16,15),2.5,a)
    text(p,'PLANO ESTUDIO / BORRADOR PARA REVISION',(W-110,15),2,a)
    vp=p.add_viewport(center=(W/2,45+vh/2),size=(vw,vh),view_center_point=((x0+x1)/2,(y0+y1)/2),view_height=vh*scale,dxfattribs={'layer':'VIEWPORTS'})
    vp.dxf.flags = vp.dxf.flags | 16384
    return out

def render(d, paper=False, pdf=False):
    target=d.layouts.get('PE_Entrega') if paper else d.modelspace()
    backend=pymupdf.PyMuPdfBackend() if pdf else svg.SVGBackend()
    cfg=config.Configuration(background_policy=config.BackgroundPolicy.WHITE,color_policy=config.ColorPolicy.BLACK)
    Frontend(RenderContext(d),backend,config=cfg).draw_layout(target)
    if paper:
        page=layout.Page.from_dxf_layout(target)
        settings=layout.Settings(scale=1,fit_page=False)
    else:
        page=layout.Page(300,220,margins=layout.Margins.all(8)); settings=layout.Settings()
    if not pdf: return backend.get_string(page,settings=settings)
    data=backend.get_pdf_bytes(page,settings=settings)
    if paper:
        # El backend redondea el tamaño de página a puntos enteros. Mantener A3/A4 exactos.
        import pymupdf as fitz
        output=fitz.open(stream=data,filetype='pdf')
        output[0].set_mediabox(fitz.Rect(0,0,page.width*72/25.4,page.height*72/25.4))
        data=output.tobytes()
        output.close()
    return data

INSTRUCTIONS='''Eres un asistente CAD 2D. Devuelve SOLO un objeto JSON {"summary":"explicación breve", "assumptions":["supuestos y límites"], "operations":[...]}. No Markdown. Todas las coordenadas y tamaños están en MILÍMETROS, eje Y hacia arriba. No ejecutes código. No inventes medidas del edificio existente: si faltan, indica tus supuestos; para trabajo nuevo puedes proponer medidas explícitas. Genera geometría a escala real 1:1. Tipos de operaciones:
wall: {type,start:[x,y],end:[x,y],thickness:150,openings:[{offset:1000,width:900,kind:"door"|"window"|"gap"}],layer:"MUROS"}. start/end son eje del muro; offset medido desde start. Huecos sin solapar y dentro del muro. La puerta abre a la izquierda del vector del muro, bisagra al inicio del hueco. Los muros se dibujan por segmentos; resuelve encuentros y evita duplicar muros compartidos. No uses rectángulos para cerrar huecos de puertas.
line: {type,start,end,layer}; polyline: {type,points:[[x,y],...],closed:true,layer}; rect: {type,origin:[x,y],width,height,layer}; circle: {type,center,radius,layer}; arc: {type,center,radius,start_angle,end_angle,layer}; text: {type,text,at:[x,y],height:120,layer:"TEXTOS"}; dimension: {type,p1:[x,y],p2:[x,y],distance:400,layer:"COTAS"}; move: {type,handles:["AB"],delta:[dx,dy]}; delete: {type,handles:["AB"]}.
Usa SOLO esos tipos y sus campos indicados. Máximo 500 operaciones. El contexto incluye entidades del dibujo existente con handles para mover o borrar; nunca inventes handles. Las operaciones se AÑADEN al plano actual: no redibujes lo que ya existe. Para reemplazar geometría, borra las entidades concretas antes. Los muebles pueden ser esquemáticos, pero añade detalles interiores para reconocerlos. Mantén puertas y recorridos libres; la herramienta NO valida normativa ni colisiones automáticamente. Para plantas completas incluye cotas generales, nombres, grosores de muros y puertas, e informa lo pendiente de comprobar. Si no puedes cumplir una petición sin información esencial, devuelve operations vacía y explica la pregunta en summary. La lámina se prepara aparte en la interfaz.'''

def example():
    return {'summary':'Ejemplo: estudio de 6 × 4 m entre ejes de muros, puerta y ventana.','assumptions':['Dimensiones entre ejes; muros de 150 mm.','Mobiliario esquemático; revisar encuentros y circulación.'], 'operations':[
        {'type':'wall','start':[0,0],'end':[6000,0],'thickness':150,'openings':[{'offset':800,'width':900,'kind':'door'}]},
        {'type':'wall','start':[6000,0],'end':[6000,4000],'thickness':150,'openings':[]},
        {'type':'wall','start':[6000,4000],'end':[0,4000],'thickness':150,'openings':[{'offset':2000,'width':1800,'kind':'window'}]},
        {'type':'wall','start':[0,4000],'end':[0,0],'thickness':150,'openings':[]},
        {'type':'rect','origin':[300,1700],'width':1400,'height':2000},
        {'type':'rect','origin':[380,3150],'width':560,'height':400},
        {'type':'rect','origin':[1060,3150],'width':560,'height':400},
        {'type':'line','start':[300,3000],'end':[1700,3000],'layer':'MOBILIARIO'},
        {'type':'rect','origin':[4400,2900],'width':1300,'height':650},
        {'type':'circle','center':[5050,2550],'radius':260},
        {'type':'rect','origin':[3000,300],'width':2400,'height':600},
        {'type':'line','start':[4200,300],'end':[4200,900],'layer':'MOBILIARIO'},
        {'type':'text','text':'ESTUDIO','at':[2400,2000],'height':180},
        {'type':'text','text':'24 m2 entre ejes','at':[2350,1750],'height':110},
        {'type':'dimension','p1':[0,0],'p2':[6000,0],'distance':-600},
        {'type':'dimension','p1':[6000,0],'p2':[6000,4000],'distance':-600}
    ]}
