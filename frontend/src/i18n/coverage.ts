import {
  comparisonChangeKinds,
  exportJobStates,
  scheduleStates,
  workspaceCommandTypes,
} from "../api/types";
import {
  businessLabelRegistries,
  constraintIds,
  officialAllowedActions,
  officialWorkspaceViews,
} from "./business-labels";
import { enUSMessages } from "./dictionaries/en-US";
import { zhCNMessages } from "./dictionaries/zh-CN";
import {
  authorizationDetailReasons,
  errorLabelRegistries,
  productErrorCategories,
  productErrorCodes,
  workspaceControlReasons,
} from "./error-labels";
import { supportedLocales, terminologyVersion } from "./types";

export interface I18nCoverageResult {
  readonly terminologyVersion: typeof terminologyVersion;
  readonly locales: typeof supportedLocales;
  readonly messageKeyCount: number;
  readonly registryValueCount: number;
  readonly missing: readonly string[];
}

function missingKeys(
  registryName: string,
  expected: readonly string[],
  actual: Readonly<Record<string, unknown>>,
): string[] {
  return expected
    .filter((value) => !Object.hasOwn(actual, value))
    .map((value) => `${registryName}:${value}`);
}

export function inspectI18nCoverage(): I18nCoverageResult {
  const enKeys = Object.keys(enUSMessages).sort();
  const zhKeys = Object.keys(zhCNMessages).sort();
  const missing = [
    ...enKeys.filter((key) => !Object.hasOwn(zhCNMessages, key)).map((key) => `zh-CN:${key}`),
    ...zhKeys.filter((key) => !Object.hasOwn(enUSMessages, key)).map((key) => `en-US:${key}`),
    ...missingKeys("scheduleState", scheduleStates, businessLabelRegistries.scheduleState),
    ...missingKeys("exportJobState", exportJobStates, businessLabelRegistries.exportJobState),
    ...missingKeys("workspaceView", officialWorkspaceViews, businessLabelRegistries.workspaceView),
    ...missingKeys("command", workspaceCommandTypes, businessLabelRegistries.command),
    ...missingKeys("allowedAction", officialAllowedActions, businessLabelRegistries.allowedAction),
    ...missingKeys("changeKind", comparisonChangeKinds, businessLabelRegistries.changeKind),
    ...missingKeys("constraint", constraintIds, businessLabelRegistries.constraint),
    ...missingKeys("productCategory", productErrorCategories, errorLabelRegistries.productCategory),
    ...missingKeys("productCode", productErrorCodes, errorLabelRegistries.productCode),
    ...missingKeys("workspaceReason", workspaceControlReasons, errorLabelRegistries.workspaceReason),
    ...missingKeys("authorizationDetail", authorizationDetailReasons, errorLabelRegistries.authorizationDetail),
  ];
  const registryValueCount =
    scheduleStates.length +
    exportJobStates.length +
    officialWorkspaceViews.length +
    workspaceCommandTypes.length +
    officialAllowedActions.length +
    comparisonChangeKinds.length +
    constraintIds.length +
    productErrorCategories.length +
    productErrorCodes.length +
    workspaceControlReasons.length +
    authorizationDetailReasons.length;
  return {
    terminologyVersion,
    locales: supportedLocales,
    messageKeyCount: enKeys.length,
    registryValueCount,
    missing,
  };
}

export function assertI18nCoverage(): I18nCoverageResult {
  const result = inspectI18nCoverage();
  if (result.missing.length > 0) {
    throw new TypeError(`i18n coverage is incomplete: ${result.missing.join(", ")}`);
  }
  return result;
}
