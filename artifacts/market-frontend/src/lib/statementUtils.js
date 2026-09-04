export const formatStatementDate = (value) => {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '—';
  return date.toLocaleDateString('ar-EG', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  });
};

export const formatStatementTime = (value) => {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  return date.toLocaleTimeString('ar-EG', {
    hour: '2-digit',
    minute: '2-digit',
  });
};

export const formatStatementDateTime = (value) => {
  const date = formatStatementDate(value);
  const time = formatStatementTime(value);
  return time ? `${date} — ${time}` : date;
};

export const formatStatementMoney = (value) =>
  `${new Intl.NumberFormat('en-US', {
    maximumFractionDigits: 2,
  }).format(Number(value) || 0)} ر.ي`;

const formatQuantity = (value) =>
  new Intl.NumberFormat('en-US', { maximumFractionDigits: 2 }).format(Number(value) || 0);

export const formatPurchaseQuantity = (item = {}) => {
  const isCarton = item.unit === 'carton' || item.return_unit === 'carton' || item.cartons != null;
  if (!isCarton) return `${formatQuantity(item.quantity)} قطعة`;

  const cartons = Number(item.cartons ?? item.quantity ?? 0);
  const piecesPerCarton = Number(item.pieces_per_carton || 0);
  const pieces = piecesPerCarton > 0 ? cartons * piecesPerCarton : Number(item.quantity || 0);
  const piecesLabel = pieces > 0 && Math.abs(pieces - cartons) > 0.001
    ? ` — ${formatQuantity(pieces)} قطعة`
    : '';
  return `${formatQuantity(cartons)} كرتون${piecesLabel}`;
};