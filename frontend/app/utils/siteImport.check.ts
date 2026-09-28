import { deflateRawSync } from 'node:zlib'
import { parseCell, parseTables, readImportTables, templateCsv, templateExcel, templateSheets, templateXlsx, type ImportField } from './siteImport'

const fields: ImportField[] = [
  { key: 'area_m2', label: 'Общая площадь склада', unit: 'м²', kind: 'number', group: 'Площадь' },
  { key: 'has_wms', label: 'Наличие WMS', unit: '', kind: 'bool', group: 'Инфраструктура' },
  { key: 'floors_count', label: 'Количество этажей', unit: 'шт', kind: 'int', group: 'Площадь' },
]

const sheets = templateSheets(fields, { area_m2: 12000, has_wms: true, floors_count: null }, [
  { process_code: 'order_picking', name: 'Сборка товаров', flow_per_day: 400 },
])

const csv = templateCsv(sheets)
if (!csv.startsWith('\uFEFF')) throw new Error('шаблон CSV без BOM')
const fromCsv = parseTables(await readImportTables(new TextEncoder().encode(csv).buffer, 'parametry.csv'), fields)
if (fromCsv.site.find((row) => row.key === 'area_m2')?.raw !== '12000') throw new Error(`CSV не вернул площадь: ${JSON.stringify(fromCsv)}`)
if (!fromCsv.site.some((row) => row.key === 'has_wms' && row.raw === 'true')) throw new Error('CSV не вернул WMS')
if (fromCsv.tasks[0]?.process_code !== 'order_picking' || fromCsv.tasks[0]?.flow_per_day !== '400') throw new Error(`CSV не вернул процесс: ${JSON.stringify(fromCsv.tasks)}`)

const xls = templateExcel(sheets)
const fromXls = parseTables(await readImportTables(new TextEncoder().encode(xls).buffer, 'parametry.xls'), fields)
if (fromXls.site.find((row) => row.key === 'area_m2')?.raw !== '12000') throw new Error('Excel XML не вернул площадь')
if (fromXls.tasks[0]?.process_code !== 'order_picking') throw new Error('Excel XML не вернул процесс')

if (parseCell('да', 'bool') !== true || parseCell('1 200,5', 'number') !== 1200.5 || parseCell('3', 'int') !== 3) {
  throw new Error('разбор ячеек')
}

const shared = `<?xml version="1.0"?><sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="4" uniqueCount="4"><si><t>Ключ</t></si><si><t>Параметр</t></si><si><t>Значение</t></si><si><t>area_m2</t></si></sst>`
const sheet = `<?xml version="1.0"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row r="1"><c r="A1" t="s"><v>0</v></c><c r="B1" t="s"><v>1</v></c><c r="C1" t="s"><v>2</v></c></row><row r="2"><c r="A2" t="s"><v>3</v></c><c r="B2" t="inlineStr"><is><t>Общая площадь склада</t></is></c><c r="C2"><v>15000</v></c></row></sheetData></worksheet>`

const crcTable = Array.from({ length: 256 }, (_, n) => {
  let c = n
  for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1
  return c >>> 0
})
const crc32 = (data: Buffer) => {
  let c = 0xffffffff
  for (const byte of data) c = crcTable[(c ^ byte) & 0xff]! ^ (c >>> 8)
  return (c ^ 0xffffffff) >>> 0
}

const zipStore = (files: [string, string][]) => {
  const chunks: Buffer[] = []
  const central: Buffer[] = []
  let offset = 0
  for (const [name, text] of files) {
    const raw = Buffer.from(text)
    const data = deflateRawSync(raw)
    const nameBuf = Buffer.from(name)
    const local = Buffer.alloc(30)
    local.writeUInt32LE(0x04034b50, 0)
    local.writeUInt16LE(20, 4)
    local.writeUInt16LE(8, 8)
    local.writeUInt32LE(crc32(raw), 14)
    local.writeUInt32LE(data.length, 18)
    local.writeUInt32LE(raw.length, 22)
    local.writeUInt16LE(nameBuf.length, 26)
    chunks.push(local, nameBuf, data)
    const cen = Buffer.alloc(46)
    cen.writeUInt32LE(0x02014b50, 0)
    cen.writeUInt16LE(20, 6)
    cen.writeUInt16LE(8, 10)
    cen.writeUInt32LE(crc32(raw), 16)
    cen.writeUInt32LE(data.length, 20)
    cen.writeUInt32LE(raw.length, 24)
    cen.writeUInt16LE(nameBuf.length, 28)
    cen.writeUInt32LE(offset, 42)
    central.push(cen, nameBuf)
    offset += local.length + nameBuf.length + data.length
  }
  const centralBuf = Buffer.concat(central)
  const end = Buffer.alloc(22)
  end.writeUInt32LE(0x06054b50, 0)
  end.writeUInt16LE(files.length, 8)
  end.writeUInt16LE(files.length, 10)
  end.writeUInt32LE(centralBuf.length, 12)
  end.writeUInt32LE(offset, 16)
  return Buffer.concat([...chunks, centralBuf, end])
}

const xlsx = zipStore([
  ['xl/sharedStrings.xml', shared],
  ['xl/worksheets/sheet1.xml', sheet],
])
const fromXlsx = parseTables(await readImportTables(xlsx.buffer.slice(xlsx.byteOffset, xlsx.byteOffset + xlsx.byteLength), 'parametry.xlsx'), fields)
if (fromXlsx.site.find((row) => row.key === 'area_m2')?.raw !== '15000') throw new Error(`xlsx не вернул площадь: ${JSON.stringify(fromXlsx)}`)

const made = templateXlsx(sheets)
const fromTemplate = parseTables(await readImportTables(made.buffer.slice(made.byteOffset, made.byteOffset + made.byteLength), 'parametry-ploshchadki.xlsx'), fields)
if (fromTemplate.site.find((row) => row.key === 'area_m2')?.raw !== '12000') throw new Error(`шаблон xlsx не вернул площадь: ${JSON.stringify(fromTemplate)}`)
if (fromTemplate.site.find((row) => row.key === 'has_wms')?.raw !== 'true') throw new Error('шаблон xlsx не вернул WMS')
if (fromTemplate.tasks[0]?.process_code !== 'order_picking' || fromTemplate.tasks[0]?.flow_per_day !== '400') throw new Error(`шаблон xlsx не вернул процесс: ${JSON.stringify(fromTemplate.tasks)}`)
const packed = new TextDecoder().decode(made)
for (const width of ['27.5', '42.6640625', '15', '23']) {
  if (!packed.includes(`width="${width}"`)) throw new Error(`в шаблоне нет ширины столбца ${width}`)
}

console.log('siteImport ok')
