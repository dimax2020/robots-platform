import { fileStem, pickReportSheets, toCsv, toExcelXml } from './exportTables'

const disclaimer = 'Результат является предварительной оценкой и требует верификации при обследовании объекта.'
const all = [
  { name: 'Паспорт проекта', rows: [['Имя проекта', 'Склад Юг'], ['CAPEX', '12,5']] },
  { name: 'Параметры объекта', headed: true, rows: [['Параметр', 'Значение'], ['Площадь', '12 000']] },
  { name: 'Сценарии', headed: true, rows: [['Сценарий', 'CAPEX'], ['Покупка', '12,5']] },
  { name: 'Формулы', headed: true, rows: [['Блок', 'Формула'], ['Часы', 'a+b']] },
  { name: 'Допущения', headed: true, rows: [['Параметр', 'Значение'], ['Тариф', '7,2']] },
]

const onlyMatch = pickReportSheets(all, { match: true, economy: false, whatif: false })
if (onlyMatch.some((sheet) => sheet.name === 'Формулы' || sheet.name === 'Допущения')) throw new Error('в файл попал снятый раздел')
if (!onlyMatch.some((sheet) => sheet.name === 'Сценарии')) throw new Error('нет листа подбора')
if (!onlyMatch.some((sheet) => sheet.name === 'Паспорт проекта')) throw new Error('нет обложки')

const csv = toCsv(onlyMatch, disclaimer)
if (!csv.startsWith('\uFEFF')) throw new Error('CSV без BOM: Excel не откроет кириллицу')
if (!csv.includes('Паспорт проекта')) throw new Error('CSV без секции паспорта')
if (!csv.includes('Склад Юг')) throw new Error('CSV без имени проекта')
if (csv.includes('Формулы')) throw new Error('CSV содержит снятые формулы')
if (!csv.includes(';')) throw new Error('CSV без разделителя для Excel')

const xls = toExcelXml(onlyMatch, disclaimer)
if (!xls.includes('Excel.Sheet')) throw new Error('Excel без SpreadsheetML')
if (!xls.includes('Паспорт проекта')) throw new Error('Excel без листа паспорта')
if (!xls.includes(disclaimer)) throw new Error('Excel без оговорки')
if (xls.includes('>Формулы<') || xls.includes('Допущения')) throw new Error('Excel содержит снятый раздел')
if (!xls.includes('ss:Width=')) throw new Error('Excel без ширины столбцов')
if (!xls.includes('#161C1A')) throw new Error('Excel без заливки шапки')
if (!xls.includes('ss:StyleID="head"')) throw new Error('Excel без стиля шапки')
if (!xls.includes('WrapText="1"')) throw new Error('Excel без переноса текста')

const stem = fileStem('Склад Внуково-Юг, 12 000 м²', new Date('2026-09-27T12:00:00Z'))
if (!stem.includes('Склад') || !stem.includes('2026-09-27')) throw new Error(`плохое имя файла: ${stem}`)

console.log('exportTables ok')
