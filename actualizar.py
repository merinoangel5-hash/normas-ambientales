"""Revisa El Peruano y agrega a normas.json las normas ambientales nuevas.

Lo ejecuta GitHub Actions cada mañana (ver .github/workflows/actualizar.yml).
Abre la página de Normas Legales en un navegador (Playwright) y pide la lista
de normas de cada fecha, igual que el buscador de la web.
"""
import json
import re
import sys
import unicodedata
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ARCHIVO = Path(__file__).resolve().parent / "normas.json"
LIMA = timezone(timedelta(hours=-5))
MAX_DIAS = 31

G1 = "MINAM · OEFA · SENACE"
G2 = "ANA · MIDAGRI · SERNANP · SERFOR"
G3 = "MINEM · PRODUCE · MTC · VIVIENDA"
G4 = "Regionales y municipales"
G5 = "Otras entidades"


def sin_tildes(s):
    return "".join(c for c in unicodedata.normalize("NFD", s or "") if unicodedata.category(c) != "Mn").lower()


# Sectores que siempre son ambientales
SECTOR_AMBIENTAL = re.compile(r"ambiente|evaluacion y fiscalizacion ambiental|certificacion ambiental|areas naturales|"
                              r"recursos forestales|forestal y de fauna|autoridad nacional del agua")
# Temas ambientales en la sumilla
TEMA_AMBIENTAL = re.compile(
    r"ambiental|recurso[s]? hidric|agua[s]? (subterrane|residual|superficial)|uso de agua|vertimiento|reuso|"
    r"\beca\b|\blmp\b|limites maximos permisibles|estandares de calidad|residuos solidos(?!.*arbitri)|"
    r"calidad del aire|emision(es)? de contaminantes|ruido|suelo|sitios contaminados|"
    r"\beia\b|impacto ambiental|igafom|\bigac\b|instrumento de gestion|terminos de referencia|consultoras ambientales|"
    r"cierre de minas|plan de cierre|pasivo|relave|petitorios mineros|area[s]? natural|omec|humedal|bofedal|"
    r"biodiversidad|fauna silvestre|forestal|cambio climatico|zonificacion ecologica|ordenamiento territorial|"
    r"cuenca|glaciar|pesca|acuicultura|recursos naturales|monitoreo ambiental|fiscalizacion ambiental")
EXCLUIR = re.compile(r"autorizan viaje|arbitrios|emision mecanizada|transferencia financiera|"
                     r"aceptan renuncia(?!.*(oefa|senace|sernanp|ana\b))|requisitos fitosanitarios|"
                     r"escala de ingresos|extradicion|precios de referencia")

TEMAS = [
    (r"igafom|\bigac\b|pequena mineria|mineria artesanal", "IGAFOM y pequeña minería"),
    (r"cierre|pasivo|garantia", "Cierre y garantías"),
    (r"petitorio|concesion minera|mineria|minero", "Minería y áreas restringidas"),
    (r"humedal|bofedal|biodiversidad|especie", "Biodiversidad y humedales"),
    (r"area[s]? natural|omec|conservacion", "Áreas de conservación"),
    (r"sitios contaminados|suelo", "Suelos y sitios contaminados"),
    (r"residuos", "Residuos sólidos"),
    (r"aire|emision|ruido", "Calidad del aire y emisiones"),
    (r"cambio climatico|adaptacion|mitigacion", "Cambio climático"),
    (r"subterrane", "Agua subterránea"),
    (r"agua|hidric|riego|vertimiento|reuso|cuenca", "Agua y riego"),
    (r"saneamiento", "Saneamiento"),
    (r"forestal|fauna", "Forestal y fauna"),
    (r"pesca|acuicultura|pesquer", "Pesca y acuicultura"),
    (r"hidrocarburo", "Hidrocarburos"),
    (r"zonificacion|ordenamiento", "Ordenamiento territorial"),
    (r"eia|impacto ambiental|certificacion|evaluacion ambiental|terminos de referencia|consultora", "Certificación ambiental"),
    (r"designan|encargan|renuncia|conforman|comite|comision", "Institucional"),
]


def grupo_y_entidad(sector, numero):
    s = sin_tildes(sector)
    n = numero.upper()
    if "OEFA" in n or "evaluacion y fiscalizacion" in s:
        return G1, "OEFA"
    if "SENACE" in n or "certificacion ambiental" in s:
        return G1, "SENACE"
    if "SERNANP" in n or "areas naturales" in s:
        return G2, "SERNANP"
    if "SERFOR" in n:
        return G2, "SERFOR"
    if "OSINFOR" in n or "recursos forestales" in s:
        return G2, "OSINFOR"
    if re.search(r"\bANA\b", n) or "autoridad nacional del agua" in s:
        return G2, "ANA"
    if s.startswith("ambiente"):
        return G1, "MINAM" if "MINAM" in n else ("SENAMHI" if "SENAMHI" in n else "MINAM")
    if "agrario" in s:
        return G2, "MIDAGRI"
    if "energia y minas" in s:
        return G3, "MINEM"
    if "produce" in s or "produccion" in s:
        return G3, "PRODUCE"
    if "transportes" in s:
        return G3, "MTC"
    if "vivienda" in s:
        return G3, "VIVIENDA"
    if s.startswith("gobierno regional") or s.startswith("municipalidad"):
        nombre = re.sub(r"\s*publicaci[oó]n digital\s*$", "", sector, flags=re.I).strip().title()
        nombre = nombre.replace(" De ", " de ").replace(" Del ", " del ").replace(" La ", " la ")
        return G4, nombre
    return G5, sector.title()


def clasificar(item):
    t = sin_tildes(item["sumilla"])
    s = sin_tildes(item["sector"])
    if EXCLUIR.search(t):
        return False
    if SECTOR_AMBIENTAL.search(s):
        return True
    return bool(TEMA_AMBIENTAL.search(t))


def tema_de(texto):
    t = sin_tildes(texto)
    for patron, nombre in TEMAS:
        if re.search(patron, t):
            return nombre
    return "Gestión ambiental"


def prioridad_de(texto, estado, grupo, tema):
    t = sin_tildes(texto)
    if tema == "Institucional":
        return "baja"
    if estado == "consulta" and grupo in (G1, G2, G3):
        return "alta"
    if re.search(r"igafom|\bigac\b|vertimiento|reuso|\beca\b|\blmp\b|limites maximos|estandares de calidad|"
                 r"plan de cierre|cierre de minas|eia|impacto ambiental|terminos de referencia|"
                 r"licencia de uso|derecho de uso de agua|reglamento", t):
        return "alta"
    if grupo == G4 or re.search(r"subvencion|financ|comite|comunidad de practica", t):
        return "baja" if grupo != G4 or not re.search(r"gestion ambiental|evaluacion ambiental", t) else "media"
    return "media"


def id_de(url, numero, fecha):
    m = re.search(r"/dispositivo/(NL|EX)/([\w-]+)", url)
    if m:
        return f"{m.group(1)}-{m.group(2)}"
    limpio = re.sub(r"[^A-Za-z0-9]+", "-", numero).strip("-")[:60]
    return f"DIG-{fecha}-{limpio}"


JS_LISTA = r"""
async ([desde, hasta]) => {
  const body = new URLSearchParams({cddesde: desde, cdhasta: hasta, btnBuscar: ''});
  const r = await fetch('/Normas/Filtro?dateparam=', {method: 'POST', body,
    headers: {'X-Requested-With': 'XMLHttpRequest', 'Content-Type': 'application/x-www-form-urlencoded'}});
  const html = await r.text();
  const d = new DOMParser().parseFromString(html, 'text/html');
  return [...d.querySelectorAll('article')].map(a => {
    const ps = [...a.querySelectorAll('.ediciones_texto p')];
    return {
      sector: (a.querySelector('h4')?.textContent || '').trim(),
      numero: (a.querySelector('h5')?.textContent || '').trim().replace(/\s+/g, ' '),
      url: a.querySelector('h5 a')?.href || '',
      fecha: ((ps[0]?.textContent || '').match(/\d\d\/\d\d\/\d{4}/) || [''])[0],
      sumilla: (ps[1]?.textContent || '').trim().replace(/\s+/g, ' ')
    };
  });
}
"""

JS_TEXTO = r"""
async (url) => {
  try {
    const h = await fetch(url).then(r => r.text());
    const d = new DOMParser().parseFromString(h, 'text/html');
    const t = (d.body.innerText || d.body.textContent || '').replace(/\s+/g, ' ');
    const i = t.search(/SE RESUELVE|SE DECRETA|DECRETA:|RESUELVE:|ORDENANZA:/i);
    return t.slice(i > 0 ? i : 0, (i > 0 ? i : 0) + 2500);
  } catch (e) { return ''; }
}
"""


def plazo_de(fecha_iso, texto):
    """Plazo de comentarios: día siguiente a la publicación + N días calendario - 1."""
    t = sin_tildes(texto)
    m = re.search(r"plazo de\s+(?:[a-z]+\s+)?\(?(\d{1,3})\)?\s+dias (calendario|habiles|utiles)", t)
    if not m:
        return None
    n, tipo = int(m.group(1)), m.group(2)
    d = date.fromisoformat(fecha_iso)
    if tipo == "calendario":
        return (d + timedelta(days=n)).isoformat()
    k = 0
    while k < n:
        d += timedelta(days=1)
        if d.weekday() < 5:
            k += 1
    return d.isoformat()


def correo_de(texto):
    m = re.search(r"[\w.+-]+@[\w-]+\.gob\.pe", texto)
    return m.group(0) if m else None


def main():
    datos = json.loads(ARCHIVO.read_text(encoding="utf-8"))
    normas = datos.get("normas", [])
    ids = {n["id"] for n in normas}
    clave = lambda num, f: f + "|" + re.sub(r"[^0-9a-rt-z]", "", sin_tildes(num))
    claves = {clave(n["numero"], n["fecha"]) for n in normas}

    hoy = datetime.now(LIMA).date()
    ultimo = date.fromisoformat(datos.get("revisadoHasta", (hoy - timedelta(days=2)).isoformat()))
    desde = min(ultimo + timedelta(days=1), hoy - timedelta(days=1))
    desde = max(desde, hoy - timedelta(days=MAX_DIAS))
    fmt = lambda d: d.strftime("%d/%m/%Y")

    from playwright.sync_api import sync_playwright

    nuevas = []
    with sync_playwright() as p:
        nav = p.chromium.launch()
        pag = nav.new_page(locale="es-PE", user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/131.0 Safari/537.36"))
        pag.goto("https://diariooficial.elperuano.pe/Normas", wait_until="networkidle", timeout=90000)
        lista = pag.evaluate(JS_LISTA, [fmt(desde), fmt(hoy)])
        print(f"El Peruano: {len(lista)} normas entre {desde} y {hoy}")
        if not lista:
            print("No se encontraron normas. Puede que El Peruano haya cambiado su página o bloqueado la consulta.")

        texto_pag = None
        for it in lista:
            if not it["url"] or not it["fecha"] or not clasificar(it):
                continue
            d, m, a = it["fecha"].split("/")
            fecha = f"{a}-{m}-{d}"
            nid = id_de(it["url"], it["numero"], fecha)
            if nid in ids or clave(it["numero"], fecha) in claves:
                continue
            grupo, entidad = grupo_y_entidad(it["sector"], it["numero"])
            sum_t = sin_tildes(it["sumilla"])
            estado = "consulta" if re.search(r"publicacion del proyecto|disponen (la )?publicacion.*proyecto|prepublica", sum_t) else "vigente"
            tema = tema_de(it["sumilla"])
            resumen = it["sumilla"].rstrip(".") + "."
            plazo = None
            if estado == "consulta" and "busquedas.elperuano.pe" in it["url"]:
                if texto_pag is None:
                    texto_pag = pag.context.new_page()
                    texto_pag.goto("https://busquedas.elperuano.pe/", timeout=60000)
                texto = texto_pag.evaluate(JS_TEXTO, it["url"])
                plazo = plazo_de(fecha, texto)
                correo = correo_de(texto)
                extra = []
                if plazo:
                    extra.append(f"Comentarios hasta aprox. el {date.fromisoformat(plazo).strftime('%d/%m/%Y')}")
                if correo:
                    extra.append(f"correo: {correo}")
                if extra:
                    resumen += " " + "; ".join(extra) + "."
            norma = {
                "id": nid, "fecha": fecha, "entidad": entidad, "grupo": grupo,
                "dependencia": it["sector"].title(), "numero": it["numero"],
                "titulo": it["sumilla"], "resumen": resumen + " (Resumen automático: revisa el texto oficial.)",
                "tema": tema, "estado": estado,
                "prioridad": prioridad_de(it["sumilla"], estado, grupo, tema),
                "url": it["url"],
                "pdf": it["url"] + "/pdf" if "busquedas.elperuano.pe/dispositivo" in it["url"] else it["url"],
                "fuente": "El Peruano (extraordinaria)" if "/EX/" in it["url"] else
                          ("El Peruano (publicación digital)" if "epdoc2" in it["url"] else "El Peruano"),
            }
            if plazo:
                norma["plazo"] = plazo
            nuevas.append(norma)
            ids.add(nid)
            claves.add(clave(it["numero"], fecha))
        nav.close()

    if not lista:
        sys.exit(1)

    normas.extend(nuevas)
    normas.sort(key=lambda n: n["fecha"], reverse=True)
    datos.update({
        "normas": normas,
        "ultimaRevision": hoy.isoformat(),
        "revisadoHasta": hoy.isoformat(),
        "nota": f"{len(nuevas)} normas nuevas hoy" if nuevas else "Sin normas ambientales nuevas hoy",
    })
    ARCHIVO.write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Normas nuevas: {len(nuevas)}")
    for n in nuevas:
        print(f"  [{n['prioridad']}] {n['entidad']} · {n['numero']} · {n['titulo'][:90]}")


if __name__ == "__main__":
    main()
