import { test } from "node:test";
import assert from "node:assert/strict";
import { formatDate, formatMoney, isNegative, isZero } from "./format.ts";

test("formatMoney groups thousands without using floating point", () => {
  assert.equal(formatMoney("1100.00"), "1,100.00");
  assert.equal(formatMoney("1234567.89", "AUD"), "AUD 1,234,567.89");
  assert.equal(formatMoney("0.30"), "0.30");
  assert.equal(formatMoney("-50.00"), "−50.00");
  assert.equal(formatMoney("999999999999999.99"), "999,999,999,999,999.99"); // beyond float precision
  assert.equal(formatMoney(null), "—");
});

test("zero and negative detection", () => {
  assert.ok(isZero("0.00"));
  assert.ok(isZero("-0.00"));
  assert.ok(!isZero("0.01"));
  assert.ok(isNegative("-0.01"));
  assert.ok(!isNegative("-0.00"));
});

test("formatDate never shifts business dates across timezones", () => {
  assert.equal(formatDate("2026-03-31"), "31 Mar 2026");
  assert.equal(formatDate("2024-02-29"), "29 Feb 2024");
  assert.equal(formatDate(undefined), "—");
});
