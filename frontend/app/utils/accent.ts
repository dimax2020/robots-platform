/** Статьи вроде пусконаладки: их название и сумма рисуются жирнее остальных. */
export const isAccent = (key?: string | null, label?: string | null) => {
  const blob = `${key ?? ''} ${label ?? ''}`.toLowerCase()
  return blob.includes('commission') || blob.includes('пусконалад') || blob.includes('пнр')
}
