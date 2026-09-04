import { useEffect, useMemo, useRef, useState } from "react";

import type {
  DemoPresentationConfiguration,
  PublicationReference,
  ScenarioManifest,
  UrgentOrderCommand,
  UrgentOrderInput,
} from "../api/types";
import { useModalFocus } from "../app/useModalFocus";
import { shortId } from "../domain/copy";

interface UrgentOrderPanelProps {
  readonly configuration: DemoPresentationConfiguration;
  readonly manifest: ScenarioManifest;
  readonly publication: PublicationReference;
  readonly pending: UrgentOrderCommand | null;
  readonly busy: boolean;
  readonly onSubmit: (input: UrgentOrderInput) => Promise<boolean>;
  readonly onClose: () => void;
}

interface FormState {
  route: string;
  quantity: string;
  due: string;
  priority: UrgentOrderInput["priority_class"];
  note: string;
}

function localInputValue(value: string): string {
  const date = new Date(value);
  const parts = new Intl.DateTimeFormat("zh-CN", {
    timeZone: "Asia/Shanghai",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).formatToParts(date);
  const part = (type: Intl.DateTimeFormatPartTypes) =>
    parts.find((item) => item.type === type)?.value ?? "00";
  return `${part("year")}-${part("month")}-${part("day")}T${part("hour")}:${part("minute")}`;
}

function initialState(
  configuration: DemoPresentationConfiguration,
  manifest: ScenarioManifest,
  pending: UrgentOrderCommand | null,
): FormState {
  if (pending !== null) {
    return {
      route: pending.route_template_id,
      quantity: String(pending.quantity),
      due: pending.due_at_local.slice(0, 16),
      priority: pending.priority_class,
      note: pending.note ?? "",
    };
  }
  const recommended =
    configuration.route_templates.find(
      (route) => route.template_id === "CNC-ROUTE-5",
    ) ?? configuration.route_templates[0];
  return {
    route: recommended?.template_id ?? "",
    quantity: "5",
    due: localInputValue(
      new Date(
        Date.parse(manifest.horizon_start_utc) + 60 * 60 * 1000 * 60,
      ).toISOString(),
    ),
    priority: "URGENT",
    note: "Showcase 固定加急精密套筒",
  };
}

export function UrgentOrderPanel({
  configuration,
  manifest,
  publication,
  pending,
  busy,
  onSubmit,
  onClose,
}: UrgentOrderPanelProps) {
  const [form, setForm] = useState(() =>
    initialState(configuration, manifest, pending),
  );
  const [confirming, setConfirming] = useState(false);
  const [errors, setErrors] = useState<Readonly<Record<string, string>>>({});
  const headingRef = useRef<HTMLHeadingElement>(null);
  const quantityRef = useRef<HTMLInputElement>(null);
  const dueRef = useRef<HTMLInputElement>(null);
  const noteRef = useRef<HTMLInputElement>(null);
  const dialogRef = useModalFocus<HTMLElement>(confirming, {
    onEscape: () => setConfirming(false),
    escapeDisabled: busy,
  });
  const selectedRoute = configuration.route_templates.find(
    (route) => route.template_id === form.route,
  );
  const selectedPriority = configuration.priority_classes.find(
    (priority) => priority.class_id === form.priority,
  );
  const minDue = localInputValue(manifest.horizon_start_utc);
  const maxDue = localInputValue(manifest.horizon_end_utc);

  useEffect(() => {
    headingRef.current?.focus();
  }, []);

  const validated = useMemo(() => {
    const next: Record<string, string> = {};
    const quantity = Number(form.quantity);
    if (selectedRoute === undefined) next.route = "请选择一条批准路线。";
    if (!Number.isInteger(quantity) || quantity < 1 || quantity > 50) {
      next.quantity = "数量须为 1～50 的整数。";
    }
    if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(form.due)) {
      next.due = "请选择完整的本地交期。";
    } else if (form.due <= minDue || form.due > maxDue) {
      next.due = "交期须晚于当前仿真时钟，且不超过排程周期。";
    }
    if (selectedPriority === undefined) next.priority = "请选择订单优先级。";
    if (form.note.length > 200) next.note = "备注不能超过 200 个字符。";
    return { errors: next, quantity };
  }, [form, maxDue, minDue, selectedPriority, selectedRoute]);

  const review = () => {
    setErrors(validated.errors);
    if (Object.keys(validated.errors).length === 0) {
      setConfirming(true);
      return;
    }
    window.setTimeout(() => {
      if (validated.errors.quantity) quantityRef.current?.focus();
      else if (validated.errors.due) dueRef.current?.focus();
      else if (validated.errors.note) noteRef.current?.focus();
    }, 0);
  };

  const confirm = async () => {
    if (selectedRoute === undefined || selectedPriority === undefined) return;
    const accepted = await onSubmit({
      route_template_id: selectedRoute.template_id,
      quantity: validated.quantity,
      due_at_local: `${form.due}:00`,
      priority_class: selectedPriority.class_id,
      note: form.note.trim() || null,
    });
    if (accepted) setConfirming(false);
  };

  return (
    <section className="urgent-panel" aria-labelledby="urgent-title">
      <div className="urgent-panel__heading">
        <div>
          <p className="eyebrow">第四步 · 现场事件</p>
          <h2 ref={headingRef} id="urgent-title" tabIndex={-1}>插入加急订单</h2>
          <p>填写业务信息即可；运行、基线和事件身份由服务端安全生成。</p>
        </div>
        <button
          className="icon-button icon-button--light"
          type="button"
          aria-label="关闭加急订单表单"
          onClick={onClose}
          disabled={busy}
        >
          ×
        </button>
      </div>

      {pending !== null && (
        <div className="recovery-banner" role="status">
          <strong>已恢复待提交命令</strong>
          <span>为保证幂等安全，本次重试必须保持原输入不变。</span>
        </div>
      )}

      <div className="baseline-strip">
        <span>当前已发布仿真基线</span>
        <strong title={publication.schedule_version_id}>
          {shortId(publication.schedule_version_id)}
        </strong>
        <small>只读 · 提交前服务端会再次校验</small>
      </div>

      <fieldset
        className="route-fieldset"
        disabled={busy || pending !== null}
        aria-describedby={errors.route ? "urgent-route-error" : undefined}
      >
        <legend>选择产品路线</legend>
        <div className="route-grid">
          {configuration.route_templates.map((route) => (
            <label
              className={`route-card ${form.route === route.template_id ? "route-card--selected" : ""}`}
              key={route.template_id}
            >
              <input
                type="radio"
                name="route"
                value={route.template_id}
                checked={form.route === route.template_id}
                onChange={(event) =>
                  setForm((current) => ({ ...current, route: event.target.value }))
                }
              />
              <span className="route-card__count">{route.operation_count} 道工序</span>
              <strong>{route.product_family_zh}</strong>
              <small>{route.operation_names_zh.join(" → ")}</small>
            </label>
          ))}
        </div>
        {errors.route && <span id="urgent-route-error" className="field-error">{errors.route}</span>}
      </fieldset>

      <div className="urgent-fields">
        <label>
          <span>订单数量</span>
          <input
            ref={quantityRef}
            type="number"
            min="1"
            max="50"
            step="1"
            value={form.quantity}
            disabled={busy || pending !== null}
            onChange={(event) =>
              setForm((current) => ({ ...current, quantity: event.target.value }))
            }
            aria-invalid={errors.quantity ? "true" : undefined}
            aria-describedby={`urgent-quantity-help${errors.quantity ? " urgent-quantity-error" : ""}`}
          />
          <small id="urgent-quantity-help">1～50 件</small>
          {errors.quantity && <span id="urgent-quantity-error" className="field-error" role="alert">{errors.quantity}</span>}
        </label>
        <label>
          <span>要求交期（北京时间）</span>
          <input
            ref={dueRef}
            type="datetime-local"
            min={minDue}
            max={maxDue}
            value={form.due}
            disabled={busy || pending !== null}
            onChange={(event) =>
              setForm((current) => ({ ...current, due: event.target.value }))
            }
            aria-invalid={errors.due ? "true" : undefined}
            aria-describedby={`urgent-due-help${errors.due ? " urgent-due-error" : ""}`}
          />
          <small id="urgent-due-help">必须位于当前排程周期内</small>
          {errors.due && <span id="urgent-due-error" className="field-error" role="alert">{errors.due}</span>}
        </label>
        <label>
          <span>优先级</span>
          <select
            value={form.priority}
            disabled={busy || pending !== null}
            aria-describedby="urgent-priority-help"
            onChange={(event) =>
              setForm((current) => ({
                ...current,
                priority: event.target.value as FormState["priority"],
              }))
            }
          >
            {configuration.priority_classes.map((priority) => (
              <option value={priority.class_id} key={priority.class_id}>
                {priority.label_zh} · 权重 {priority.priority_weight}
              </option>
            ))}
          </select>
          <small id="urgent-priority-help">权重来自批准的仿真策略</small>
        </label>
        <label className="urgent-note">
          <span>演示备注（可选）</span>
          <input
            ref={noteRef}
            type="text"
            maxLength={200}
            value={form.note}
            disabled={busy || pending !== null}
            onChange={(event) =>
              setForm((current) => ({ ...current, note: event.target.value }))
            }
            aria-describedby={`urgent-note-help${errors.note ? " urgent-note-error" : ""}`}
          />
          <small id="urgent-note-help">{form.note.length}/200</small>
          {errors.note && <span id="urgent-note-error" className="field-error" role="alert">{errors.note}</span>}
        </label>
      </div>

      <div className="urgent-panel__footer">
        <p>
          提交后将保留已完成、正在加工、硬锁和冻结窗口内任务，再自动重排其余工序。
        </p>
        <button
          className="button button--primary"
          type="button"
          onClick={review}
          disabled={busy}
        >
          核对并提交插单
        </button>
      </div>

      {confirming && selectedRoute && selectedPriority && (
        <div className="dialog-backdrop" role="presentation">
          <section
            ref={dialogRef}
            className="confirmation-dialog confirmation-dialog--wide"
            role="dialog"
            tabIndex={-1}
            aria-modal="true"
            aria-labelledby="urgent-confirm-title"
            aria-describedby="urgent-confirm-boundary"
          >
            <span className="dialog-icon dialog-icon--urgent" aria-hidden="true">!</span>
            <p className="eyebrow">提交前最后核对</p>
            <h2 id="urgent-confirm-title">确认接收这张加急订单？</h2>
            <dl className="urgent-review">
              <div><dt>产品路线</dt><dd>{selectedRoute.product_family_zh} · {selectedRoute.operation_count} 道工序</dd></div>
              <div><dt>数量</dt><dd>{validated.quantity} 件</dd></div>
              <div><dt>要求交期</dt><dd>{form.due.replace("T", " ")}（北京时间）</dd></div>
              <div><dt>优先级</dt><dd>{selectedPriority.label_zh} · 权重 {selectedPriority.priority_weight}</dd></div>
              <div><dt>重排基线</dt><dd>{shortId(publication.schedule_version_id)}</dd></div>
            </dl>
            <div id="urgent-confirm-boundary" className="dialog-boundary">
              <strong>新方案只会保存为草稿</strong>
              <span>不会自动发布，也不会替换当前仿真基线</span>
            </div>
            <div className="dialog-actions">
              <button
                className="button button--quiet"
                type="button"
                onClick={() => setConfirming(false)}
                disabled={busy}
              >
                返回修改
              </button>
              <button
                data-autofocus
                className="button button--primary"
                type="button"
                onClick={() => void confirm()}
                disabled={busy}
              >
                {busy ? "正在提交…" : "确认插单并自动重排"}
              </button>
            </div>
          </section>
        </div>
      )}
    </section>
  );
}
