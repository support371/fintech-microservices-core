export type DepositStatus = 'created' | 'received' | 'settled';
export type CardStatus = 'requested' | 'issued' | 'frozen';

export type Deposit = {
  id: string;
  userId: string;
  amount: number;
  currency: string;
  status: DepositStatus;
  idempotencyKey: string;
  createdAt: string;
};

export type BitcoinCard = {
  id: string;
  userId: string;
  nickname: string;
  status: CardStatus;
  createdAt: string;
};

export type OperationLog = {
  id: string;
  operation: string;
  actorId: string;
  createdAt: string;
};

const deposits = new Map<string, Deposit>();
const cards = new Map<string, BitcoinCard>();
const cardRequestsByIdempotencyKey = new Map<string, BitcoinCard>();
const operations: OperationLog[] = [];

function addOperation(operation: string, actorId: string) {
  operations.unshift({
    id: crypto.randomUUID(),
    operation,
    actorId,
    createdAt: new Date().toISOString(),
  });
}

export function listDeposits(userId: string): Deposit[] {
  return [...deposits.values()].filter((d) => d.userId === userId);
}

export function createDeposit(input: {
  userId: string;
  amount: number;
  currency: string;
  idempotencyKey: string;
}): { deposit: Deposit; idempotent: boolean } {
  const existing = [...deposits.values()].find((d) => d.idempotencyKey === input.idempotencyKey);
  if (existing) return { deposit: existing, idempotent: true };

  const deposit: Deposit = {
    id: crypto.randomUUID(),
    userId: input.userId,
    amount: input.amount,
    currency: input.currency,
    status: 'created',
    idempotencyKey: input.idempotencyKey,
    createdAt: new Date().toISOString(),
  };

  deposits.set(deposit.id, deposit);
  addOperation(`deposit_created:${deposit.id}`, input.userId);

  return { deposit, idempotent: false };
}

export function listCards(userId: string): BitcoinCard[] {
  return [...cards.values()].filter((c) => c.userId === userId);
}

export function requestCard(input: {
  userId: string;
  nickname: string;
  idempotencyKey: string;
}): { card?: BitcoinCard; error?: string; idempotent?: boolean } {
  const idempotentHit = cardRequestsByIdempotencyKey.get(input.idempotencyKey);
  if (idempotentHit) {
    return { card: idempotentHit, idempotent: true };
  }

  const activeExists = [...cards.values()].some(
    (card) => card.userId === input.userId && (card.status === 'requested' || card.status === 'issued'),
  );

  if (activeExists) {
    return { error: 'You already have an active/requested card.' };
  }

  const card: BitcoinCard = {
    id: crypto.randomUUID(),
    userId: input.userId,
    nickname: input.nickname,
    status: 'requested',
    createdAt: new Date().toISOString(),
  };

  cards.set(card.id, card);
  cardRequestsByIdempotencyKey.set(input.idempotencyKey, card);
  addOperation(`card_requested:${card.id}`, input.userId);

  return { card, idempotent: false };
}

export function getOperations(limit = 20): OperationLog[] {
  return operations.slice(0, limit);
}
