/** Выгрузка таблиц отчёта: CSV для Excel с кириллицей и многолистовой SpreadsheetML. */

export interface TableSheet {
  name: string
  rows: string[][]
  /** Первая строка — шапка таблицы. У паспорта её нет: там подпись и значение. */
  headed?: boolean
}

/* Обложка в файле есть всегда. Остальные листы повторяют галочки конструктора. */
const COVER_SHEETS = ['Паспорт проекта', 'Параметры объекта']
const MATCH_SHEETS = ['Сценарии', 'Вывод', 'Процессы', 'Роботы']
const ECONOMY_SHEETS = ['Формулы', 'Подстановка']
const WHATIF_SHEETS = ['Допущения', 'Чувствительность']

export const pickReportSheets = (
  sheets: TableSheet[],
  flags: { match: boolean; economy: boolean; whatif: boolean },
) => {
  const keep = new Set<string>(COVER_SHEETS)
  if (flags.match) MATCH_SHEETS.forEach((name) => keep.add(name))
  if (flags.economy) ECONOMY_SHEETS.forEach((name) => keep.add(name))
  if (flags.whatif) WHATIF_SHEETS.forEach((name) => keep.add(name))
  return sheets.filter((sheet) => keep.has(sheet.name))
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

/* Ширина в пунктах. Длинный текст не растягивает столбец на весь экран, а переносится, и строка становится выше. */
const colWidth = (rows: string[][], index: number) => {
  let chars = 12
  for (const row of rows) {
    for (const part of (row[index] ?? '').split(/\r?\n/)) chars = Math.max(chars, Math.min(part.length, 64))
  }
  return Math.round(chars * 7 + 20)
}

const rowHeight = (row: string[], widths: number[]) => {
  let lines = 1
  row.forEach((cell, index) => {
    const per = Math.max(8, Math.floor(((widths[index] ?? 90) - 16) / 7))
    const count = (cell ?? '').split(/\r?\n/).reduce((sum, part) => sum + Math.max(1, Math.ceil((part.length || 1) / per)), 0)
    lines = Math.max(lines, count)
  })
  return Math.min(150, Math.max(20, lines * 16))
}

const cellXml = (value: string, style: string) => `<Cell ss:StyleID="${style}"><Data ss:Type="String">${xml(value ?? '')}</Data></Cell>`

const styleXml = (id: string, fill: string, color: string, bold: boolean) => `<Style ss:ID="${id}">
  <Alignment ss:Horizontal="Left" ss:Vertical="Center" ss:WrapText="1"/>
  <Font ss:FontName="Calibri" ss:Size="11" ss:Color="${color}"${bold ? ' ss:Bold="1"' : ''}/>
  <Interior ss:Color="${fill}" ss:Pattern="Solid"/>
  <Borders>
    <Border ss:Position="Bottom" ss:LineStyle="Continuous" ss:Weight="1" ss:Color="#D7E0DC"/>
    <Border ss:Position="Left" ss:LineStyle="Continuous" ss:Weight="1" ss:Color="#D7E0DC"/>
    <Border ss:Position="Right" ss:LineStyle="Continuous" ss:Weight="1" ss:Color="#D7E0DC"/>
    <Border ss:Position="Top" ss:LineStyle="Continuous" ss:Weight="1" ss:Color="#D7E0DC"/>
  </Borders>
</Style>`

export const toExcelXml = (sheets: TableSheet[], disclaimer: string) => {
  const styles = [
    styleXml('note', '#FFF4E0', '#5C3700', false),
    styleXml('head', '#161C1A', '#F1F5F3', true),
    styleXml('odd', '#FFFFFF', '#1C2421', false),
    styleXml('even', '#F3F7F5', '#1C2421', false),
    styleXml('label', '#E7F3EE', '#1C2421', true),
  ].join('')
  const worksheets = sheets.map((sheet) => {
    const width = Math.max(1, ...sheet.rows.map((row) => row.length), 1)
    const padded = sheet.rows.map((row) => Array.from({ length: width }, (_, index) => row[index] ?? ''))
    const widths = Array.from({ length: width }, (_, index) => colWidth([[disclaimer], ...padded], index))
    const columns = widths.map((size) => `<Column ss:AutoFitWidth="0" ss:Width="${size}"/>`).join('')
    const note = `<Row ss:AutoFitHeight="0" ss:Height="${rowHeight([disclaimer], [widths[0] ?? 200])}"><Cell ss:StyleID="note" ss:MergeAcross="${Math.max(0, width - 1)}"><Data ss:Type="String">${xml(disclaimer)}</Data></Cell></Row>`
    const gap = '<Row ss:AutoFitHeight="0" ss:Height="8"/>'
    const body = padded.map((row, index) => {
      const height = rowHeight(row, widths)
      const cells = row.map((value, column) => {
        if (sheet.headed && index === 0) return cellXml(value, 'head')
        if (!sheet.headed && column === 0) return cellXml(value, 'label')
        return cellXml(value, index % 2 === 0 ? 'even' : 'odd')
      }).join('')
      return `<Row ss:AutoFitHeight="0" ss:Height="${height}">${cells}</Row>`
    }).join('')
    return `<Worksheet ss:Name="${xml(sheetName(sheet.name))}"><Table>${columns}${note}${gap}${body}</Table></Worksheet>`
  }).join('')
  return `<?xml version="1.0" encoding="UTF-8"?>
<?mso-application progid="Excel.Sheet"?>
<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet" xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet"><Styles>${styles}</Styles>${worksheets}</Workbook>`
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
