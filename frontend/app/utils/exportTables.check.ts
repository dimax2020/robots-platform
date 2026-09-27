import { fileStem, toCsv, toExcelXml } from './exportTables'

const disclaimer = 'Результат является предварительной оценкой и требует верификации при обследовании объекта.'
const sheets = [
  { name: 'Паспорт проекта', rows: [['Имя проекта', 'Склад Юг'], ['CAPEX', '12,5']] },
  { name: 'Сценарии экономики', rows: [['Сценарий', 'CAPEX'], ['Покупка', '12,5']] },
]

const csv = toCsv(sheets, disclaimer)
if (!csv.startsWith('\uFEFF')) throw new Error('CSV без BOM: Excel не откроет кириллицу')
if (!csv.includes('Паспорт проекта')) throw new Error('CSV без секции паспорта')
if (!csv.includes('Склад Юг')) throw new Error('CSV без имени проекта')
if (!csv.includes(';')) throw new Error('CSV без разделителя для Excel')

const xls = toExcelXml(sheets, disclaimer)
if (!xls.includes('Excel.Sheet')) throw new Error('Excel без SpreadsheetML')
if (!xls.includes('Паспорт проекта')) throw new Error('Excel без листа паспорта')
if (!xls.includes(disclaimer)) throw new Error('Excel без оговорки')

const stem = fileStem('Склад Внуково-Юг, 12 000 м²', new Date('2026-09-27T12:00:00Z'))
if (!stem.includes('Склад') || !stem.includes('2026-09-27')) throw new Error(`плохое имя файла: ${stem}`)

console.log('exportTables ok')
