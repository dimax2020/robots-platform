/** Выгрузка таблиц отчёта: CSV для Excel с кириллицей и многолистовой SpreadsheetML. */

export interface TableSheet {
  name: string
  rows: string[][]
}

const BOM = '\uFEFF'
const SEP = ';'

const csvCell = (value: string) => {
  const text = value ?? ''
  if (/[;"\n\r]/.test(text)) return `"${text.replace(/"/g, '""')}"`
  return text
}

export const fileStem = (name: string, date = new Date()) => {
  const slug = name.replace(/[^\p{L}\p{N}]+/gu, '_').replace(/^_|_$/g, '').slice(0, 72) || 'otchet'
  return `${slug}_${date.toISOString().slice(0, 10)}`
}

export const toCsv = (sheets: TableSheet[], disclaimer: string) => {
  const lines = [disclaimer, '']
  for (const sheet of sheets) {
    lines.push(sheet.name)
    for (const row of sheet.rows) lines.push(row.map(csvCell).join(SEP))
    lines.push('')
  }
  return BOM + lines.join('\r\n')
}

const xml = (value: string) => value
  .replace(/&/g, '&amp;')
  .replace(/</g, '&lt;')
  .replace(/>/g, '&gt;')
  .replace(/"/g, '&quot;')

const sheetName = (name: string) => name.replace(/[:\\/*?[\]]/g, ' ').slice(0, 31) || 'Лист'

export const toExcelXml = (sheets: TableSheet[], disclaimer: string) => {
  const worksheets = sheets.map((sheet) => {
    const rows = [[disclaimer], [], ...sheet.rows]
      .map((row) => `<Row>${row.map((cell) => `<Cell><Data ss:Type="String">${xml(cell ?? '')}</Data></Cell>`).join('')}</Row>`)
      .join('')
    return `<Worksheet ss:Name="${xml(sheetName(sheet.name))}"><Table>${rows}</Table></Worksheet>`
  }).join('')
  return `<?xml version="1.0" encoding="UTF-8"?>
<?mso-application progid="Excel.Sheet"?>
<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet" xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet">${worksheets}</Workbook>`
}

export const downloadBytes = (filename: string, mime: string, bytes: Uint8Array) => {
  const copy = new Uint8Array(bytes.byteLength)
  copy.set(bytes)
  const blob = new Blob([copy], { type: mime })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  URL.revokeObjectURL(url)
}

export const downloadText = (filename: string, mime: string, text: string) => {
  const blob = new Blob([text], { type: mime })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  URL.revokeObjectURL(url)
}

export const downloadDataUrl = (filename: string, dataUrl: string) => {
  const link = document.createElement('a')
  link.href = dataUrl
  link.download = filename
  link.click()
}
