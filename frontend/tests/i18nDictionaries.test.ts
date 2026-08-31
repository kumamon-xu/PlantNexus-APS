import {
  businessLabelRegistries,
  labelBusinessValue,
} from "../src/i18n/business-labels";
import { assertI18nCoverage } from "../src/i18n/coverage";
import { enUSMessages } from "../src/i18n/dictionaries/en-US";
import { zhCNMessages } from "../src/i18n/dictionaries/zh-CN";
import {
  labelErrorValue,
  localizeErrorEnvelope,
  productErrorCodes,
} from "../src/i18n/error-labels";
import { terminologyVersion } from "../src/i18n/types";

describe("TEST-FRONTEND-I18N-001 dictionary and terminology coverage", () => {
  it("keeps both versioned dictionaries key-identical", () => {
    expect(Object.keys(zhCNMessages).sort()).toEqual(Object.keys(enUSMessages).sort());
    expect(Object.keys(enUSMessages).length).toBeGreaterThan(150);
    const coverage = assertI18nCoverage();
    expect(coverage).toMatchObject({
      terminologyVersion,
      locales: ["zh-CN", "en-US"],
      missing: [],
    });
    expect(coverage.registryValueCount).toBeGreaterThan(100);
  });

  it("covers every registered product code and keeps namespace selection explicit", () => {
    for (const code of productErrorCodes) {
      expect(labelErrorValue("productCode", code, "zh-CN")).toMatchObject({
        known: true,
        raw: code,
      });
      expect(labelErrorValue("productCode", code, "en-US").label).not.toHaveLength(0);
    }
    const product = localizeErrorEnvelope(
      {
        namespace: "PRODUCT",
        category: "DATA_ERROR",
        code: "INVALID_REFERENCE",
        correlationId: "correlation-i18n-001",
        safeMessage: "safe server diagnostic",
      },
      "zh-CN",
    );
    const workspace = localizeErrorEnvelope(
      { namespace: "WORKSPACE_CONTROL", reason: "INVALID_REFERENCE" },
      "zh-CN",
    );
    expect(product.primary).toMatchObject({ known: true, raw: "INVALID_REFERENCE" });
    expect(workspace.primary).toMatchObject({ known: true, raw: "INVALID_REFERENCE" });
    expect(product.correlationId).toBe("correlation-i18n-001");
    expect(product.safeMessage).toBe("safe server diagnostic");
  });

  it("fails visibly for unknown machine values without losing raw evidence", () => {
    expect(labelBusinessValue("scheduleState", "FUTURE_STATE", "zh-CN")).toEqual({
      known: false,
      label: "未知（FUTURE_STATE）",
      raw: "FUTURE_STATE",
    });
    expect(labelErrorValue("workspaceReason", "FUTURE_REASON", "en-US")).toEqual({
      known: false,
      label: "Unknown (FUTURE_REASON)",
      raw: "FUTURE_REASON",
    });
  });

  it("uses official Chinese labels while retaining machine registries", () => {
    expect(businessLabelRegistries.scheduleState.READY_FOR_REVIEW["zh-CN"]).toBe("待评审");
    expect(businessLabelRegistries.scheduleState.PUBLISHED["en-US"]).toBe("Published internally");
    expect(businessLabelRegistries.command.PUBLISH["zh-CN"]).toBe("内部发布");
    expect(businessLabelRegistries.workspaceView.LOCKS["zh-CN"]).toBe("锁定");
    expect(businessLabelRegistries.constraint["C-011"]["zh-CN"]).toBe("计划时域");
    expect(businessLabelRegistries.executionEvent.MACHINE_UNAVAILABLE["zh-CN"]).toBe(
      "设备不可用",
    );
    expect(businessLabelRegistries.planningRunState.SOLVING["en-US"]).toBe(
      "Solving",
    );
    expect(businessLabelRegistries.changeClassification.REMOVED_BY_FACT["zh-CN"]).toBe(
      "因执行事实移除",
    );
  });
});
