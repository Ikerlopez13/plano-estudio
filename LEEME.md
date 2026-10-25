# Plano Estudio — primera versión funcional

Aplicación local para preparar planos 2D editables para AutoCAD. Incluye código fuente, interfaz en español y un ejemplo completo de estudio de 6 × 4 m. No necesitas AutoCAD para generar, visualizar o descargar el plano; ella lo necesita para continuar trabajando en AutoCAD.

## En Windows

1. Instala Python 3.12 o superior desde https://www.python.org/downloads/windows/ (incluye el lanzador `py`).
2. Extrae TODO el ZIP a una carpeta. No ejecutes el programa dentro del ZIP.
3. Haz doble clic en `INICIAR_WINDOWS.bat`. La primera vez descargará las bibliotecas necesarias; necesita Internet.
4. Se abre el navegador en `http://127.0.0.1:8765`. Mantén abierta la ventana de consola.
5. Pulsa **Cargar ejemplo** y descarga el DXF y el PDF para probarlo.

Los siguientes arranques reutilizan el entorno instalado. Si el puerto está ocupado, cierra la otra instancia. El programa escucha solo en tu propio ordenador. Para cerrarlo, pulsa Ctrl+C en la consola.

## Acceso con contraseña

La app puede exigir contraseña para entrar. Se controla con la variable de entorno `PLANO_PASSWORD`:

- **En local:** si no defines `PLANO_PASSWORD`, la app queda abierta (cómodo para ti). Si la defines (en `.env.local` o `.env`), pedirá contraseña también en local.
- **En internet:** `PLANO_PASSWORD` es **obligatoria**. Sin ella, cualquiera con el enlace podría usar la app y gastar tu saldo de OpenAI.

La clave de API (`OPENAI_API_KEY`) y la contraseña nunca se guardan en el repositorio: van en `.env.local` (local, ignorado por git) o en las variables del host (despliegue). La plantilla `.env.example` documenta todas las variables.

## Desplegar en internet (Render) con contraseña

Esta app es un servidor con estado en memoria, así que necesita un host de **proceso persistente** (Render, Railway, Fly). **No** funciona en plataformas serverless como Vercel.

Pasos en Render (plan gratuito):

1. Entra en https://render.com e inicia sesión con GitHub.
2. **New → Blueprint** y elige este repositorio. Render lee `render.yaml` y configura el servicio solo.
3. Define los secretos cuando los pida:
   - `PLANO_PASSWORD` → la contraseña de acceso (obligatoria).
   - `OPENAI_API_KEY` → opcional, solo si quieres el modo «IA conectada» sin que cada usuario meta su clave.
4. **Create**. En unos minutos tendrás una URL `https://plano-estudio-XXXX.onrender.com` protegida con contraseña.

El plan gratuito de Render «duerme» el servicio tras un rato sin uso; la primera visita tras dormir tarda unos segundos en despertar. Al despertar, el plano en memoria se reinicia: descarga el DXF antes de cerrar.

## Crear o cambiar un plano mediante este chat

No requiere configurar una API:

1. Escribe la petición y sus medidas en la aplicación.
2. Pulsa **Copiar petición para el chat**. Incluye las instrucciones del formato y el resumen del plano actual.
3. Pégalo en una conversación con ChatGPT y solicita únicamente el JSON.
4. Pega la respuesta en la aplicación y pulsa **Previsualizar propuesta**.
5. Revisa los supuestos, la geometría y las cotas. Pulsa **Aplicar al plano**.
6. Descarga el DXF y, si quieres, el PDF.

El texto estructurado se pega en esta aplicación, no en AutoCAD. No es un intérprete de Python ni de AutoLISP: solo admite operaciones CAD conocidas.

## Generación directa con IA

En **IA conectada**, introduce una clave de OpenAI API y un modelo compatible con Responses API y modo JSON. `gpt-4.1` es el valor inicial, editable según los modelos disponibles en tu cuenta. También puedes definir OPENAI_API_KEY en el entorno del servidor.

La API tiene facturación propia. No se conecta automáticamente a una suscripción de ChatGPT. La clave se mantiene en el formulario durante la sesión, no se guarda en archivos ni en almacenamiento del navegador. El servidor la utiliza para enviar a OpenAI la petición y el resumen geométrico del dibujo. Se solicita `store: false`; esto no equivale a una garantía de retención cero por parte del proveedor.

La integración está implementada; no se ha probado con una llamada real de pago porque no se ha proporcionado una clave. El modo con este chat permite trabajar sin ella. El programa no accede por sí mismo a conversaciones antiguas.

## Continuar un trabajo existente

En AutoCAD, abre el DWG y usa **Guardar como → DXF**. Trabaja en milímetros: esta versión no convierte unidades automáticamente. Importa ese DXF en la aplicación. Si el archivo no declara unidades, confirma expresamente que sus coordenadas representan milímetros.

Puedes pedir añadidos, cotas, mover o eliminar entidades identificadas. Los cambios se hacen sobre una copia en memoria y puedes deshacer los últimos 12 cambios. Los objetos no modificados se conservan a través de ezdxf; algunas entidades especializadas pueden no verse o no conservar todas sus propiedades. Prueba primero una copia de un trabajo real. El resumen enviado a la IA incluye hasta 2.000 entidades y no descompone los bloques: la edición inteligente de dibujos complejos es limitada.

## Entrega

- **DXF:** geometría a escala real 1:1 en mm, capas y cotas DIMENSION editables. Las cotas generadas no son asociativas: si mueves los objetos después, revisa o regenera las cotas.
- **Lámina:** A3 o A4 horizontal, cajetín sencillo y viewport bloqueado con la escala elegida en `PE_Entrega`. No modifica otras láminas del archivo importado. Una lámina previa llamada `PE_Entrega` se sustituye solo en la copia exportada.
- **PDF:** vectorial, con tamaño de papel exacto. Imprime a tamaño real / 100 %, sin «ajustar a página».
- Si no cabe el dibujo, la aplicación pide otra escala o papel; no lo reduce silenciosamente.
- En AutoCAD: **Abrir → DXF**, comprobar con DIST una medida conocida y **Guardar como → DWG**. Autodesk documenta esta conversión: https://help.autodesk.com/cloudhelp/2020/ENU/AutoCAD-LT/files/GUID-11AEFE3C-D05A-45C3-8604-7B6A594440F3.htm

**Descarga el DXF antes de cerrar la consola. No hay guardado automático:** el proyecto activo y el historial están en memoria. Puedes continuar otro día importando el DXF descargado.

## Alcance real de esta versión

Admite muros rectos con huecos de puerta/ventana, líneas, polilíneas, arcos, círculos, muebles esquemáticos, textos y cotas alineadas. Permite mover o eliminar entidades y añadir elementos en planos existentes. Tiene previsualización, aceptación de propuestas, deshacer y exportación.

No es AutoCAD completo ni una herramienta capaz de terminar cualquier trabajo de forma autónoma. No importa DWG directamente, ni interpreta fotografías/croquis/PDF, ni hace 3D, ni resuelve automáticamente encuentros de muros, colisiones, instalaciones, normativa o rúbricas de clase. No incluye una biblioteca profesional de bloques ni tramados de materiales. Las referencias externas y las fuentes CAD especiales no se empaquetan. Los muros del ejemplo tienen encuentros esquemáticos que deben limpiarse si el nivel de entrega lo requiere.

Límites: importación de 12 MB desde la interfaz y hasta 10.000 entidades en modelo; 500 operaciones por propuesta; hasta 30.000 entidades resultantes. La escala y la validación de estructura DXF no garantizan que una distribución sea correcta.

## Verificación

Probado en macOS con Python 3.12 y 3.14: seis pruebas del motor CAD, reapertura y auditoría DXF, cotas 6000/4000 mm, hueco de puerta, movimiento y borrado sin cambiar el original, rechazo de operaciones inválidas, escala de viewport y PDF A3. También probado el recorrido HTTP: propuesta, aplicar, deshacer, exportar DXF, importar ese DXF y exportar PDF. Interfaz verificada en navegador. No probado dentro de AutoCAD ni ejecutado en Windows; el lanzador está preparado para Windows y requiere esa comprobación en el ordenador de ella.

Para repetir pruebas: `.venv\Scripts\python.exe -m unittest test_cad.py -v`.

En macOS/Linux: crea un entorno virtual, instala `requirements.txt` y ejecuta `python app.py`. El código de la aplicación utiliza bibliotecas de terceros con sus propias licencias (ezdxf, PyMuPDF, Pillow). Antes de distribuir un producto comercial, revisa esas licencias, especialmente la de PyMuPDF.

Documentación de la API: https://developers.openai.com/api/docs/guides/structured-outputs
Documentación de exportación CAD: https://ezdxf.readthedocs.io/en/stable/addons/drawing.html
