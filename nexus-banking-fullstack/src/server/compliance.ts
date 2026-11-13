/**
 * Jurisdiction-aware compliance engine.
 *
 * Implements the risk-based KYC approach recommended by FATF:
 * allocate intensive due-diligence to high-risk customers and
 * automate low-risk verification. Transaction limits and reporting
 * thresholds adapt per jurisdiction.
 */

// ─────────────────────────────────────────────────────────────────────────────
// Jurisdiction Definitions
// ─────────────────────────────────────────────────────────────────────────────

export type Jurisdiction = "US" | "EU" | "UK" | "JP" | "AE" | "BR" | "DEFAULT";

export interface JurisdictionConfig {
  code: Jurisdiction;
  label: string;
  /** Currency Transaction Report threshold (local currency equivalent) */
  ctrThreshold: number;
  ctrCurrency: string;
  /** Maximum single deposit allowed without EDD */
  maxDepositWithoutEDD: number;
  /** Maximum single exchange order */
  maxExchangeAmount: number;
  /** Minimum KYC tier for card issuance */
  minCardKycTier: number;
  /** Required ID types for basic KYC */
  requiredIdTypes: string[];
  /** Velocity limits: max transactions per window */
  velocityWindow: { maxTransactions: number; windowHours: number };
  /** AML structuring detection window */
  structuringDetection: { windowHours: number; thresholdMultiple: number };
  /** Data protection regime */
  dataProtection: "GDPR" | "CCPA" | "PIPL" | "LGPD" | "PIPA" | "NONE";
  /** Whether enhanced due diligence is required for all customers */
  eddRequired: boolean;
}

const JURISDICTIONS: Record<Jurisdiction, JurisdictionConfig> = {
  US: {
    code: "US",
    label: "United States",
    ctrThreshold: 10_000,
    ctrCurrency: "USD",
    maxDepositWithoutEDD: 50_000,
    maxExchangeAmount: 100_000,
    minCardKycTier: 2,
    requiredIdTypes: ["passport", "drivers_license", "state_id"],
    velocityWindow: { maxTransactions: 50, windowHours: 24 },
    structuringDetection: { windowHours: 48, thresholdMultiple: 0.8 },
    dataProtection: "CCPA",
    eddRequired: false,
  },
  EU: {
    code: "EU",
    label: "European Union (AMLD5/6)",
    ctrThreshold: 10_000,
    ctrCurrency: "EUR",
    maxDepositWithoutEDD: 15_000,
    maxExchangeAmount: 100_000,
    minCardKycTier: 3,
    requiredIdTypes: ["passport", "national_id"],
    velocityWindow: { maxTransactions: 40, windowHours: 24 },
    structuringDetection: { windowHours: 48, thresholdMultiple: 0.7 },
    dataProtection: "GDPR",
    eddRequired: false,
  },
  UK: {
    code: "UK",
    label: "United Kingdom",
    ctrThreshold: 10_000,
    ctrCurrency: "GBP",
    maxDepositWithoutEDD: 15_000,
    maxExchangeAmount: 100_000,
    minCardKycTier: 3,
    requiredIdTypes: ["passport", "drivers_license"],
    velocityWindow: { maxTransactions: 40, windowHours: 24 },
    structuringDetection: { windowHours: 48, thresholdMultiple: 0.7 },
    dataProtection: "GDPR",
    eddRequired: false,
  },
  JP: {
    code: "JP",
    label: "Japan (Criminal Proceeds Prevention)",
    ctrThreshold: 2_000_000,
    ctrCurrency: "JPY",
    maxDepositWithoutEDD: 10_000_000,
    maxExchangeAmount: 50_000_000,
    minCardKycTier: 3,
    requiredIdTypes: ["passport", "residence_card", "my_number_card"],
    velocityWindow: { maxTransactions: 30, windowHours: 24 },
    structuringDetection: { windowHours: 72, thresholdMultiple: 0.6 },
    dataProtection: "PIPA",
    eddRequired: false,
  },
  AE: {
    code: "AE",
    label: "United Arab Emirates",
    ctrThreshold: 55_000,
    ctrCurrency: "AED",
    maxDepositWithoutEDD: 100_000,
    maxExchangeAmount: 200_000,
    minCardKycTier: 3,
    requiredIdTypes: ["passport", "emirates_id"],
    velocityWindow: { maxTransactions: 30, windowHours: 24 },
    structuringDetection: { windowHours: 48, thresholdMultiple: 0.75 },
    dataProtection: "NONE",
    eddRequired: false,
  },
  BR: {
    code: "BR",
    label: "Brazil (LGPD)",
    ctrThreshold: 50_000,
    ctrCurrency: "BRL",
    maxDepositWithoutEDD: 100_000,
    maxExchangeAmount: 500_000,
    minCardKycTier: 2,
    requiredIdTypes: ["cpf", "rg", "passport"],
    velocityWindow: { maxTransactions: 40, windowHours: 24 },
    structuringDetection: { windowHours: 48, thresholdMultiple: 0.8 },
    dataProtection: "LGPD",
    eddRequired: false,
  },
  DEFAULT: {
    code: "DEFAULT",
    label: "Default (FATF Baseline)",
    ctrThreshold: 10_000,
    ctrCurrency: "USD",
    maxDepositWithoutEDD: 15_000,
    maxExchangeAmount: 50_000,
    minCardKycTier: 3,
    requiredIdTypes: ["passport"],
    velocityWindow: { maxTransactions: 25, windowHours: 24 },
    structuringDetection: { windowHours: 48, thresholdMultiple: 0.7 },
    dataProtection: "NONE",
    eddRequired: true,
  },
};

export function getJurisdiction(code: string): JurisdictionConfig {
  const upper = code.toUpperCase() as Jurisdiction;
  return JURISDICTIONS[upper] ?? JURISDICTIONS.DEFAULT;
}

export function getAllJurisdictions(): JurisdictionConfig[] {
  return Object.values(JURISDICTIONS);
}

// ─────────────────────────────────────────────────────────────────────────────
// Risk Assessment
// ─────────────────────────────────────────────────────────────────────────────

export type RiskLevel = "low" | "medium" | "high" | "critical";

export interface RiskAssessment {
  level: RiskLevel;
  score: number; // 0-100
  factors: string[];
  requiresEDD: boolean;
  requiresManualReview: boolean;
  requiresCTR: boolean;
}

interface RiskInput {
  jurisdiction: Jurisdiction;
  kycTier: number;
  transactionAmount: number;
  transactionCurrency: string;
  isPEP: boolean;
  transactionCount24h: number;
  accountAgeDays: number;
}

/**
 * Compute risk assessment for a transaction.
 * Uses a weighted scoring model aligned with FATF risk-based approach.
 */
export function assessTransactionRisk(input: RiskInput): RiskAssessment {
  const config = getJurisdiction(input.jurisdiction);
  const factors: string[] = [];
  let score = 0;

  // Factor 1: Amount relative to CTR threshold
  const amountRatio = input.transactionAmount / config.ctrThreshold;
  if (amountRatio >= 1.0) {
    score += 30;
    factors.push(`Amount exceeds CTR threshold (${config.ctrCurrency} ${config.ctrThreshold})`);
  } else if (amountRatio >= config.structuringDetection.thresholdMultiple) {
    score += 20;
    factors.push("Amount near CTR threshold — potential structuring");
  } else if (amountRatio >= 0.5) {
    score += 10;
  }

  // Factor 2: KYC tier
  if (input.kycTier === 0) {
    score += 25;
    factors.push("KYC not completed");
  } else if (input.kycTier < config.minCardKycTier) {
    score += 10;
    factors.push("KYC tier below jurisdiction minimum for full access");
  }

  // Factor 3: PEP (Politically Exposed Person)
  if (input.isPEP) {
    score += 20;
    factors.push("Customer is a Politically Exposed Person (PEP)");
  }

  // Factor 4: Transaction velocity
  if (input.transactionCount24h > config.velocityWindow.maxTransactions) {
    score += 15;
    factors.push(`High velocity: ${input.transactionCount24h} transactions in 24h`);
  } else if (input.transactionCount24h > config.velocityWindow.maxTransactions * 0.7) {
    score += 8;
    factors.push("Elevated transaction velocity");
  }

  // Factor 5: Account age
  if (input.accountAgeDays < 7) {
    score += 10;
    factors.push("New account (< 7 days)");
  } else if (input.accountAgeDays < 30) {
    score += 5;
  }

  // Factor 6: Jurisdiction requires EDD for all
  if (config.eddRequired) {
    score += 10;
    factors.push("Jurisdiction requires enhanced due diligence by default");
  }

  // Clamp to 100
  score = Math.min(score, 100);

  // Determine risk level
  let level: RiskLevel;
  if (score >= 70) level = "critical";
  else if (score >= 50) level = "high";
  else if (score >= 25) level = "medium";
  else level = "low";

  return {
    level,
    score,
    factors,
    requiresEDD: score >= 50 || input.isPEP || config.eddRequired,
    requiresManualReview: score >= 70,
    requiresCTR: amountRatio >= 1.0,
  };
}

// ─────────────────────────────────────────────────────────────────────────────
// Compliance Checks
// ─────────────────────────────────────────────────────────────────────────────

export interface ComplianceResult {
  allowed: boolean;
  reason?: string;
  risk: RiskAssessment;
  flags: string[];
}

/**
 * Check if a deposit is compliant for a given jurisdiction.
 */
export function checkDepositCompliance(
  amount: number,
  currency: string,
  jurisdiction: Jurisdiction,
  kycTier: number,
  transactionCount24h: number = 0,
  accountAgeDays: number = 365,
  isPEP: boolean = false
): ComplianceResult {
  const jConfig = getJurisdiction(jurisdiction);
  const flags: string[] = [];

  const risk = assessTransactionRisk({
    jurisdiction,
    kycTier,
    transactionAmount: amount,
    transactionCurrency: currency,
    isPEP,
    transactionCount24h,
    accountAgeDays,
  });

  // Check absolute limits
  if (amount > jConfig.maxDepositWithoutEDD && !isPEP && kycTier < 3) {
    return {
      allowed: false,
      reason: `Deposit exceeds ${jConfig.ctrCurrency} ${jConfig.maxDepositWithoutEDD} — enhanced KYC required (tier 3+)`,
      risk,
      flags,
    };
  }

  if (risk.requiresCTR) {
    flags.push("CTR_REQUIRED");
  }
  if (risk.requiresManualReview) {
    flags.push("MANUAL_REVIEW");
  }
  if (risk.requiresEDD) {
    flags.push("EDD_REQUIRED");
  }

  return { allowed: true, risk, flags };
}

/**
 * Check if card issuance is compliant for a given jurisdiction.
 */
export function checkCardIssuanceCompliance(
  jurisdiction: Jurisdiction,
  kycTier: number,
  kycStatus: string
): ComplianceResult {
  const jConfig = getJurisdiction(jurisdiction);
  const flags: string[] = [];

  const risk = assessTransactionRisk({
    jurisdiction,
    kycTier,
    transactionAmount: 0,
    transactionCurrency: jConfig.ctrCurrency,
    isPEP: false,
    transactionCount24h: 0,
    accountAgeDays: 365,
  });

  if (kycStatus !== "approved") {
    return {
      allowed: false,
      reason: "KYC must be approved before card issuance",
      risk,
      flags,
    };
  }

  if (kycTier < jConfig.minCardKycTier) {
    return {
      allowed: false,
      reason: `Jurisdiction ${jConfig.label} requires KYC tier ${jConfig.minCardKycTier}+ for card issuance (current: ${kycTier})`,
      risk,
      flags,
    };
  }

  return { allowed: true, risk, flags };
}

/**
 * Check if an exchange order is compliant.
 */
export function checkExchangeCompliance(
  fiatAmount: number,
  fiatCurrency: string,
  jurisdiction: Jurisdiction,
  kycTier: number,
  transactionCount24h: number = 0,
  accountAgeDays: number = 365,
  isPEP: boolean = false
): ComplianceResult {
  const jConfig = getJurisdiction(jurisdiction);
  const flags: string[] = [];

  const risk = assessTransactionRisk({
    jurisdiction,
    kycTier,
    transactionAmount: fiatAmount,
    transactionCurrency: fiatCurrency,
    isPEP,
    transactionCount24h,
    accountAgeDays,
  });

  if (fiatAmount > jConfig.maxExchangeAmount) {
    return {
      allowed: false,
      reason: `Exchange exceeds jurisdiction limit of ${jConfig.ctrCurrency} ${jConfig.maxExchangeAmount}`,
      risk,
      flags,
    };
  }

  if (risk.requiresCTR) flags.push("CTR_REQUIRED");
  if (risk.requiresManualReview) flags.push("MANUAL_REVIEW");
  if (risk.requiresEDD) flags.push("EDD_REQUIRED");

  return { allowed: true, risk, flags };
}

export class ComplianceError extends Error {
  public flags: string[];
  public risk: RiskAssessment;

  constructor(message: string, flags: string[], risk: RiskAssessment) {
    super(message);
    this.name = "ComplianceError";
    this.flags = flags;
    this.risk = risk;
  }
}
