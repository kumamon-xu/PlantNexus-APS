import type { ConfirmationKind } from "../app/useDemoStory";
import { useModalFocus } from "../app/useModalFocus";

interface ConfirmationDialogProps {
  readonly kind: ConfirmationKind;
  readonly busy: boolean;
  readonly onConfirm: () => void;
  readonly onCancel: () => void;
}

export function ConfirmationDialog({
  kind,
  busy,
  onConfirm,
  onCancel,
}: ConfirmationDialogProps) {
  const dialogRef = useModalFocus<HTMLElement>(kind !== null, {
    onEscape: onCancel,
    escapeDisabled: busy,
  });

  if (kind === null) return null;
  const isReset = kind === "RESET";
  return (
    <div className="dialog-backdrop" role="presentation">
      <section
        ref={dialogRef}
        className="confirmation-dialog"
        role="dialog"
        tabIndex={-1}
        aria-modal="true"
        aria-labelledby="confirmation-title"
        aria-describedby="confirmation-detail"
      >
        <span className="dialog-icon" aria-hidden="true">
          {isReset ? "↻" : "✓"}
        </span>
        <p className="eyebrow">需要明确确认</p>
        <h2 id="confirmation-title">
          {isReset ? "重置当前演示运行？" : "设为当前仿真基线？"}
        </h2>
        <p id="confirmation-detail">
          {isReset
            ? "系统会创建新的本地演示运行并在自检成功后原子切换。当前运行进入有限保留归档，正在执行任务时不会允许重置。"
            : "该操作会显式批准当前待确认版本，并只发布到仿真内部目标。后续动态重排将以它为基线。"}
        </p>
        <div className="dialog-boundary">
          <strong>仅限仿真环境</strong>
          <span>{isReset ? "不会删除当前运行后再尝试初始化" : "不会获得生产发布权限"}</span>
        </div>
        <div className="dialog-actions">
          <button className="button button--quiet" type="button" onClick={onCancel} disabled={busy}>
            取消
          </button>
          <button
            data-autofocus
            className="button button--primary"
            type="button"
            onClick={onConfirm}
            disabled={busy}
          >
            {busy ? "正在提交…" : isReset ? "确认重置" : "确认并发布仿真基线"}
          </button>
        </div>
      </section>
    </div>
  );
}
