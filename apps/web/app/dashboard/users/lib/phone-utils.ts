/**
 * Rwanda phone number utilities for Garuka (E.164 compliance)
 * Rwandan mobile numbers are +250 7X XXX XXXX (MTN: 078, 079; Airtel: 072, 073).
 */

export interface PhoneValidationResult {
  isValid: boolean;
  normalized: string;
  carrier?: "MTN Rwanda" | "Airtel Rwanda" | "Rwanda Mobile" | "Other";
  error?: string;
}

export function normalizeRwandaPhone(input: string): string {
  if (!input) return "";
  // Strip all whitespace, dashes, parentheses
  let cleaned = input.replace(/[\s\-\(\)\.]/g, "");

  // If starts with 00250 -> +250
  if (cleaned.startsWith("00250")) {
    cleaned = "+" + cleaned.slice(2);
  }

  // If starts with 250 (without +)
  if (cleaned.startsWith("250") && !cleaned.startsWith("+")) {
    cleaned = "+" + cleaned;
  }

  // If starts with local 07... (10 digits) -> +2507...
  if (cleaned.startsWith("07") && cleaned.length === 10) {
    cleaned = "+250" + cleaned.slice(1);
  }

  // If starts with 7... (9 digits) -> +2507...
  if (/^7\d{8}$/.test(cleaned)) {
    cleaned = "+250" + cleaned;
  }

  return cleaned;
}

export function validateRwandaPhone(input: string): PhoneValidationResult {
  if (!input || !input.trim()) {
    return { isValid: false, normalized: "", error: "Phone number is required for USSD." };
  }

  const normalized = normalizeRwandaPhone(input.trim());

  // Check E.164 format for Rwanda: +250 followed by 7 and 8 digits
  const rwandaPattern = /^\+250(7[2389]\d{7})$/;
  const generalRwanda = /^\+250(7\d{8})$/;

  if (rwandaPattern.test(normalized)) {
    let carrier: PhoneValidationResult["carrier"] = "Rwanda Mobile";
    if (normalized.startsWith("+25078") || normalized.startsWith("+25079")) {
      carrier = "MTN Rwanda";
    } else if (normalized.startsWith("+25072") || normalized.startsWith("+25073")) {
      carrier = "Airtel Rwanda";
    }
    return { isValid: true, normalized, carrier };
  }

  if (generalRwanda.test(normalized)) {
    return { isValid: true, normalized, carrier: "Rwanda Mobile" };
  }

  // Give helpful contextual hint
  if (normalized.startsWith("+250")) {
    if (normalized.length < 13) {
      return {
        isValid: false,
        normalized,
        error: `Too short (${13 - normalized.length} digit${13 - normalized.length > 1 ? "s" : ""} missing). Format: +250788123456`,
      };
    }
    if (normalized.length > 13) {
      return {
        isValid: false,
        normalized,
        error: `Too long (${normalized.length - 13} extra digit${normalized.length - 13 > 1 ? "s" : ""}). Format: +250788123456`,
      };
    }
    return {
      isValid: false,
      normalized,
      error: "Invalid Rwandan mobile prefix. Must start with 078, 079, 072, or 073.",
    };
  }

  return {
    isValid: false,
    normalized,
    error: "Enter a valid Rwandan mobile number (e.g. 0788123456 or +250788123456).",
  };
}
