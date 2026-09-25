const AMR = '/img/robot-amr-pallet.png'
const FORK = '/img/robot-forklift.png'
const CUBE = '/img/robot-cube.png'
const PICK = '/img/robot-g2p.png'
const ARM = '/img/robot-arm.png'
const COBOT = '/img/robot-cobot.png'
const CLEAN = '/img/robot-uv.png'
const DRONE = '/img/robot-drone.png'
const PATROL = '/img/robot-patrol.png'

const BY_PROCESS: Record<string, string> = {
  pallet_transport: AMR,
  baggage_transport: AMR,
  rack_placement: FORK,
  cart_towing: FORK,
  apron_transport: FORK,
  auto_pallet_storage: CUBE,
  order_picking: PICK,
  tote_delivery: PICK,
  medicine_delivery: PICK,
  biomaterial_delivery: PICK,
  parcel_sorting: ARM,
  palletizing: ARM,
  ward_service: COBOT,
  passenger_service: COBOT,
  floor_cleaning: CLEAN,
  facade_washing: DRONE,
  roof_inspection: DRONE,
  territory_inspection: DRONE,
  inventory: DRONE,
  perimeter_security: PATROL,
}

const byName = (name: string) => {
  const text = name.toLowerCase().replace(/ё/g, 'е')
  if (/дрон|бпла|бвс|коптер|квадрокоптер|vtol|supercam|гескан/.test(text)) return DRONE
  if (/поломо|уборк|пылесос|cleanbot|scrubber|scrub/.test(text)) return CLEAN
  if (/патрул|охран/.test(text)) return PATROL
  if (/smartcube|шаттл|shuttle|as-rs|кран-штабел|система хранения/.test(text)) return CUBE
  if (/вилочн|ричтрак|погрузчик|штабел|fmr/.test(text)) return FORK
  if (/тягач|буксир|\btug\b/.test(text)) return FORK
  if (/кобот|cobot/.test(text)) return COBOT
  if (/манипулятор|паллетир|robotarm|роборук/.test(text)) return ARM
  if (/комплект|picker|goods-to-person|отборщик/.test(text)) return PICK
  if (/\bamr\b|паллет|поддон/.test(text)) return AMR
  return null
}

export const placeholderFor = (name: string, processCode?: string) =>
  byName(name) ?? (processCode ? BY_PROCESS[processCode] : null) ?? AMR

export const photoFor = (imageUrl: string | null | undefined, name: string, processCode?: string) =>
  imageUrl?.trim() ? imageUrl : placeholderFor(name, processCode)
