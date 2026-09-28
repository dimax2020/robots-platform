/** Шаблон и разбор параметров площадки: CSV, Excel XML и xlsx. */

import { toExcelXml, type TableSheet } from './exportTables'

export interface ImportField {
  key: string
  label: string
  unit: string
  kind: 'number' | 'int' | 'bool' | 'text'
  group: string
}

export const TASK_COLUMNS: { key: string; label: string; kind: 'text' | 'number' }[] = [
  { key: 'process_code', label: 'Код процесса', kind: 'text' },
  { key: 'name', label: 'Процесс', kind: 'text' },
  { key: 'flow_per_hour', label: 'Поток в час', kind: 'number' },
  { key: 'flow_per_day', label: 'Поток в сутки', kind: 'number' },
  { key: 'peak_factor', label: 'Пиковый коэффициент', kind: 'number' },
  { key: 'route_len_m', label: 'Длина маршрута, м', kind: 'number' },
  { key: 'max_load_kg', label: 'Масса тары, кг', kind: 'number' },
  { key: 't_load_s', label: 'Погрузка, с', kind: 'number' },
  { key: 't_unload_s', label: 'Разгрузка, с', kind: 'number' },
  { key: 'staff_fte_now', label: 'Персонал сейчас, чел', kind: 'number' },
]

export interface ParsedImport {
  site: { key: string; raw: string }[]
  tasks: Record<string, string>[]
  unknown: string[]
}

const norm = (value: string) => value.trim().toLowerCase().replace(/\s+/g, ' ')

const decodeXml = (value: string) => value
  .replace(/&lt;/g, '<')
  .replace(/&gt;/g, '>')
  .replace(/&quot;/g, '"')
  .replace(/&apos;/g, "'")
  .replace(/&#(\d+);/g, (_, n) => String.fromCharCode(Number(n)))
  .replace(/&amp;/g, '&')

export const parseCell = (raw: string, kind: ImportField['kind'] | 'number' | 'text'): number | boolean | string | null => {
  const text = raw.trim()
  if (!text) return null
  if (kind === 'bool') {
    const token = norm(text)
    if (['да', 'yes', 'true', '1', 'истина'].includes(token)) return true
    if (['нет', 'no', 'false', '0', 'ложь'].includes(token)) return false
    return null
  }
  if (kind === 'text') return text
  const n = Number(text.replace(/\s/g, '').replace(',', '.'))
  if (!Number.isFinite(n)) return null
  return kind === 'int' ? Math.trunc(n) : n
}

const siteHeader = (row: string[]) => {
  const cells = row.map(norm)
  const hasValue = cells.some((cell) => cell === 'значение' || cell === 'value')
  const hasName = cells.some((cell) => ['ключ', 'key', 'параметр', 'label', 'название'].includes(cell))
  return hasValue && hasName
}

const taskHeader = (row: string[]) => row.some((cell) => {
  const token = norm(cell)
  return token === 'process_code' || token === 'код процесса'
})

const columnIndex = (row: string[], names: string[]) => row.findIndex((cell) => names.includes(norm(cell)))

const lookupKey = (fields: ImportField[], token: string) => {
  const name = norm(token)
  if (!name) return ''
  return fields.find((field) => norm(field.key) === name || norm(field.label) === name)?.key ?? ''
}

const parseSiteRows = (rows: string[][], fields: ImportField[], unknown: string[]) => {
  const headerAt = rows.findIndex(siteHeader)
  if (headerAt < 0) return [] as { key: string; raw: string }[]
  const header = rows[headerAt]!
  const keyCol = columnIndex(header, ['ключ', 'key'])
  const labelCol = columnIndex(header, ['параметр', 'label', 'название'])
  const valueCol = columnIndex(header, ['значение', 'value'])
  const found: { key: string; raw: string }[] = []
  for (const row of rows.slice(headerAt + 1)) {
    if (!row.some((cell) => cell.trim())) continue
    if (siteHeader(row) || taskHeader(row)) break
    const raw = (valueCol >= 0 ? row[valueCol] : '') ?? ''
    if (!raw.trim()) continue
    const key = lookupKey(fields, keyCol >= 0 ? row[keyCol] ?? '' : '') || lookupKey(fields, labelCol >= 0 ? row[labelCol] ?? '' : '')
    if (!key) {
      unknown.push((row[labelCol] || row[keyCol] || raw).trim())
      continue
    }
    found.push({ key, raw: raw.trim() })
  }
  return found
}

const parseTaskRows = (rows: string[][]) => {
  const headerAt = rows.findIndex(taskHeader)
  if (headerAt < 0) return [] as Record<string, string>[]
  const header = rows[headerAt]!.map(norm)
  const index = new Map(TASK_COLUMNS.map((col) => [norm(col.label), col.key]))
  for (const col of TASK_COLUMNS) index.set(col.key, col.key)
  const cols = header.map((cell) => index.get(cell) ?? '')
  const tasks: Record<string, string>[] = []
  for (const row of rows.slice(headerAt + 1)) {
    if (!row.some((cell) => cell.trim())) continue
    if (siteHeader(row)) break
    const item: Record<string, string> = {}
    cols.forEach((key, i) => {
      if (key && row[i]?.trim()) item[key] = row[i]!.trim()
    })
    if (item.process_code || item.name) tasks.push(item)
  }
  return tasks
}

export const parseTables = (tables: string[][][], fields: ImportField[]): ParsedImport => {
  const unknown: string[] = []
  const site = tables.flatMap((rows) => parseSiteRows(rows, fields, unknown))
  const tasks = tables.flatMap(parseTaskRows)
  return { site, tasks, unknown }
}

const csvRows = (text: string): string[][] => {
  const source = text.replace(/^\uFEFF/, '').replace(/\r\n/g, '\n').replace(/\r/g, '\n')
  const sample = source.split('\n').slice(0, 8).join('\n')
  const delimiter = (sample.match(/;/g)?.length ?? 0) >= (sample.match(/,/g)?.length ?? 0) ? ';' : ','
  const rows: string[][] = []
  let row: string[] = []
  let cell = ''
  let quoted = false
  for (let i = 0; i < source.length; i++) {
    const ch = source[i]!
    if (quoted) {
      if (ch === '"') {
        if (source[i + 1] === '"') { cell += '"'; i += 1 } else quoted = false
      } else cell += ch
      continue
    }
    if (ch === '"') { quoted = true; continue }
    if (ch === delimiter) { row.push(cell); cell = ''; continue }
    if (ch === '\n') { row.push(cell); rows.push(row); row = []; cell = ''; continue }
    cell += ch
  }
  row.push(cell)
  if (row.some((item) => item.trim())) rows.push(row)
  return rows
}

const xmlPieces = (block: string) => [...block.matchAll(/<t[^>]*>([\s\S]*?)<\/t>/g)].map((match) => decodeXml(match[1] ?? '')).join('')

const columnOf = (ref: string) => {
  const letters = ref.replace(/[0-9]/g, '')
  let n = 0
  for (const ch of letters) n = n * 26 + ch.toUpperCase().charCodeAt(0) - 64
  return Math.max(0, n - 1)
}

const sheetRows = (xml: string, shared: string[]): string[][] => {
  const rows: string[][] = []
  for (const rowMatch of xml.matchAll(/<row\b[^>]*>([\s\S]*?)<\/row>/gi)) {
    const line: string[] = []
    for (const cell of rowMatch[1]!.matchAll(/<c\b([^>]*)(?:\/>|>([\s\S]*?)<\/c>)/g)) {
      const attrs = cell[1] ?? ''
      const body = cell[2] ?? ''
      const ref = attrs.match(/\br="([A-Z]+)\d+"/i)?.[1] ?? ''
      const at = ref ? columnOf(ref) : line.length
      const kind = attrs.match(/\bt="([^"]+)"/)?.[1] ?? ''
      const raw = body.match(/<v[^>]*>([\s\S]*?)<\/v>/)?.[1] ?? ''
      let text = ''
      if (kind === 's') text = shared[Number(raw)] ?? ''
      else if (kind === 'inlineStr') text = xmlPieces(body)
      else text = decodeXml(raw)
      while (line.length < at) line.push('')
      line[at] = text
    }
    if (line.some((item) => item.trim())) rows.push(line)
  }
  return rows
}

const excelXmlRows = (xml: string): string[][][] => {
  const sheets = [...xml.matchAll(/<Worksheet\b[^>]*>[\s\S]*?<Table\b[^>]*>([\s\S]*?)<\/Table>/g)]
  const blocks = sheets.length ? sheets.map((match) => match[1]!) : [xml]
  return blocks.map((block) => {
    const rows: string[][] = []
    for (const rowMatch of block.matchAll(/<Row\b[^>]*>([\s\S]*?)<\/Row>/g)) {
      const line: string[] = []
      for (const cell of rowMatch[1]!.matchAll(/<Cell\b([^>]*)(?:\/>|>([\s\S]*?)<\/Cell>)/g)) {
        const index = Number(cell[1]?.match(/\bss:Index="(\d+)"/)?.[1] ?? 0)
        const at = index > 0 ? index - 1 : line.length
        const data = cell[2]?.match(/<Data\b[^>]*>([\s\S]*?)<\/Data>/)?.[1] ?? ''
        while (line.length < at) line.push('')
        line[at] = decodeXml(data)
      }
      if (line.some((item) => item.trim())) rows.push(line)
    }
    return rows
  })
}

const inflateRaw = async (data: Uint8Array) => {
  const stream = new DecompressionStream('deflate-raw')
  const copy = new Uint8Array(data.byteLength)
  copy.set(data)
  const response = new Response(new Blob([copy]).stream().pipeThrough(stream))
  return new Uint8Array(await response.arrayBuffer())
}

const u16 = (view: DataView, offset: number) => view.getUint16(offset, true)
const u32 = (view: DataView, offset: number) => view.getUint32(offset, true)

const findEocd = (bytes: Uint8Array) => {
  const start = Math.max(0, bytes.length - 22 - 0xffff)
  for (let i = bytes.length - 22; i >= start; i--) {
    if (bytes[i] === 0x50 && bytes[i + 1] === 0x4b && bytes[i + 2] === 0x05 && bytes[i + 3] === 0x06) return i
  }
  return -1
}

const storeEntry = async (files: Map<string, Uint8Array>, bytes: Uint8Array, view: DataView, name: string, method: number, dataAt: number, size: number) => {
  if (!name || name.endsWith('/')) return
  const data = bytes.subarray(dataAt, dataAt + size)
  if (method === 0) files.set(name, data)
  else if (method === 8) files.set(name, await inflateRaw(data))
}

/** Центральный каталог ZIP: так читаются xlsx из Excel, где размер лежит не в локальном заголовке. */
const unzip = async (buffer: ArrayBuffer) => {
  const bytes = new Uint8Array(buffer)
  const view = new DataView(buffer)
  const files = new Map<string, Uint8Array>()
  const eocd = findEocd(bytes)
  if (eocd >= 0) {
    let cursor = u32(view, eocd + 16)
    const end = cursor + u32(view, eocd + 12)
    while (cursor + 46 <= end && u32(view, cursor) === 0x02014b50) {
      const method = u16(view, cursor + 10)
      const size = u32(view, cursor + 20)
      const nameLen = u16(view, cursor + 28)
      const extraLen = u16(view, cursor + 30)
      const commentLen = u16(view, cursor + 32)
      const local = u32(view, cursor + 42)
      const name = new TextDecoder().decode(bytes.subarray(cursor + 46, cursor + 46 + nameLen))
      const localName = u16(view, local + 26)
      const localExtra = u16(view, local + 28)
      await storeEntry(files, bytes, view, name, method, local + 30 + localName + localExtra, size)
      cursor += 46 + nameLen + extraLen + commentLen
    }
    return files
  }
  let offset = 0
  while (offset + 30 <= bytes.length && u32(view, offset) === 0x04034b50) {
    const method = u16(view, offset + 8)
    const size = u32(view, offset + 18)
    const nameLen = u16(view, offset + 26)
    const extraLen = u16(view, offset + 28)
    const name = new TextDecoder().decode(bytes.subarray(offset + 30, offset + 30 + nameLen))
    const dataAt = offset + 30 + nameLen + extraLen
    await storeEntry(files, bytes, view, name, method, dataAt, size)
    offset = dataAt + size
  }
  return files
}

const readXlsx = async (buffer: ArrayBuffer): Promise<string[][][]> => {
  const files = await unzip(buffer)
  const sharedXml = files.get('xl/sharedStrings.xml')
  const shared = sharedXml
    ? [...new TextDecoder().decode(sharedXml).matchAll(/<si\b[^>]*>([\s\S]*?)<\/si>/g)].map((match) => xmlPieces(match[1]!))
    : []
  const sheets = [...files.keys()].filter((name) => /^xl\/worksheets\/sheet\d+\.xml$/.test(name)).sort()
  return sheets.map((name) => sheetRows(new TextDecoder().decode(files.get(name)!), shared))
}

export const readImportTables = async (buffer: ArrayBuffer, filename: string): Promise<string[][][]> => {
  const head = new TextDecoder().decode(buffer.slice(0, 8))
  if (head.startsWith('PK')) return readXlsx(buffer)
  const text = new TextDecoder().decode(buffer)
  if (text.includes('<Workbook') || text.includes('<worksheet') || filename.toLowerCase().endsWith('.xls')) return excelXmlRows(text)
  return [csvRows(text)]
}

const csvCell = (value: string) => (/[;"\n\r]/.test(value) ? `"${value.replace(/"/g, '""')}"` : value)

export const templateSheets = (
  fields: ImportField[],
  site: Record<string, unknown>,
  tasks: Record<string, unknown>[],
): TableSheet[] => {
  const siteRows = [['Ключ', 'Параметр', 'Единица', 'Группа', 'Значение']]
  for (const field of fields) {
    const value = site[field.key]
    siteRows.push([field.key, field.label, field.unit, field.group, value == null || value === '' ? '' : String(value)])
  }
  const taskRows = [TASK_COLUMNS.map((col) => col.label)]
  const source = tasks.length ? tasks : [{}]
  for (const task of source) taskRows.push(TASK_COLUMNS.map((col) => {
    const value = task[col.key]
    return value == null ? '' : String(value)
  }))
  return [
    { name: 'Параметры', rows: siteRows },
    { name: 'Процессы', rows: taskRows },
  ]
}

export const templateCsv = (sheets: TableSheet[]) => {
  const lines: string[] = []
  for (const sheet of sheets) {
    lines.push(sheet.name)
    for (const row of sheet.rows) lines.push(row.map((cell) => csvCell(cell ?? '')).join(';'))
    lines.push('')
  }
  return `\uFEFF${lines.join('\r\n')}`
}

export const templateExcel = (sheets: TableSheet[]) => toExcelXml(sheets, 'Шаблон параметров площадки. Заполните столбец «Значение» и лист «Процессы». Пустая ячейка не затирает уже введённое.')

const CRC_TABLE = new Uint32Array(256)
for (let n = 0; n < 256; n++) {
  let c = n
  for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1
  CRC_TABLE[n] = c >>> 0
}
const crc32 = (data: Uint8Array) => {
  let c = 0xffffffff
  for (const byte of data) c = CRC_TABLE[(c ^ byte) & 0xff]! ^ (c >>> 8)
  return (c ^ 0xffffffff) >>> 0
}

const zipStore = (entries: [string, Uint8Array][]) => {
  const parts: Uint8Array[] = []
  const central: Uint8Array[] = []
  let offset = 0
  for (const [name, data] of entries) {
    const nameBuf = new TextEncoder().encode(name)
    const local = new Uint8Array(30)
    const view = new DataView(local.buffer)
    view.setUint32(0, 0x04034b50, true)
    view.setUint16(4, 20, true)
    view.setUint32(14, crc32(data), true)
    view.setUint32(18, data.length, true)
    view.setUint32(22, data.length, true)
    view.setUint16(26, nameBuf.length, true)
    parts.push(local, nameBuf, data)
    const cen = new Uint8Array(46)
    const cenView = new DataView(cen.buffer)
    cenView.setUint32(0, 0x02014b50, true)
    cenView.setUint16(6, 20, true)
    cenView.setUint32(16, crc32(data), true)
    cenView.setUint32(20, data.length, true)
    cenView.setUint32(24, data.length, true)
    cenView.setUint16(28, nameBuf.length, true)
    cenView.setUint32(42, offset, true)
    central.push(cen, nameBuf)
    offset += local.length + nameBuf.length + data.length
  }
  const centralBytes = concatBytes(central)
  const end = new Uint8Array(22)
  const endView = new DataView(end.buffer)
  endView.setUint32(0, 0x06054b50, true)
  endView.setUint16(8, entries.length, true)
  endView.setUint16(10, entries.length, true)
  endView.setUint32(12, centralBytes.length, true)
  endView.setUint32(16, offset, true)
  return concatBytes([...parts, centralBytes, end])
}

const concatBytes = (chunks: Uint8Array[]) => {
  const out = new Uint8Array(chunks.reduce((sum, chunk) => sum + chunk.length, 0))
  let at = 0
  for (const chunk of chunks) {
    out.set(chunk, at)
    at += chunk.length
  }
  return out
}

const xmlText = (value: string) => value
  .replace(/&/g, '&amp;')
  .replace(/</g, '&lt;')
  .replace(/>/g, '&gt;')

const colName = (index: number) => {
  let n = index + 1
  let text = ''
  while (n > 0) {
    const rem = (n - 1) % 26
    text = String.fromCharCode(65 + rem) + text
    n = Math.floor((n - 1) / 26)
  }
  return text
}

/** Ширины листа «Параметры» как в присланном образце parametry-ploshchadki.xlsx. */
const PARAM_COL_WIDTHS = [27.5, 42.6640625, 15, 23]

const worksheetXml = (rows: string[][]) => {
  const header = rows[0] ?? []
  const sized = header[0] === 'Ключ' && header[1] === 'Параметр' && header[4] === 'Значение'
  const cols = sized
    ? `<cols>${PARAM_COL_WIDTHS.map((width, index) => `<col min="${index + 1}" max="${index + 1}" width="${width}" customWidth="1"/>`).join('')}</cols>`
    : ''
  const body = rows.map((row, rowIndex) => {
    const cells = row.map((cell, colIndex) => {
      const ref = `${colName(colIndex)}${rowIndex + 1}`
      return `<c r="${ref}" t="inlineStr"><is><t>${xmlText(cell ?? '')}</t></is></c>`
    }).join('')
    return `<row r="${rowIndex + 1}">${cells}</row>`
  }).join('')
  return `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">${cols}<sheetData>${body}</sheetData></worksheet>`
}

/** Настоящий xlsx без сжатия: его открывает Excel и тот же разбор, что загружает файл обратно. */
export const templateXlsx = (sheets: TableSheet[]) => {
  const encoder = new TextEncoder()
  const names = sheets.map((sheet, index) => ({ sheet, file: `xl/worksheets/sheet${index + 1}.xml` }))
  const workbook = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>${names.map((item, index) => `<sheet name="${xmlText(item.sheet.name)}" sheetId="${index + 1}" r:id="rId${index + 1}"/>`).join('')}</sheets></workbook>`
  const rels = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">${names.map((item, index) => `<Relationship Id="rId${index + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet${index + 1}.xml"/>`).join('')}</Relationships>`
  const content = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>${names.map((item) => `<Override PartName="/${item.file}" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>`).join('')}</Types>`
  const rootRels = `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>`
  return zipStore([
    ['[Content_Types].xml', encoder.encode(content)],
    ['_rels/.rels', encoder.encode(rootRels)],
    ['xl/workbook.xml', encoder.encode(workbook)],
    ['xl/_rels/workbook.xml.rels', encoder.encode(rels)],
    ...names.map((item) => [item.file, encoder.encode(worksheetXml(item.sheet.rows))] as [string, Uint8Array]),
  ])
}
