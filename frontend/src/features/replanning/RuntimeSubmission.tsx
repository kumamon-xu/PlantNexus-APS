import { Alert, Button, Card, Checkbox, Input, Typography } from "antd";
import { useRef, useState } from "react";
import { parseCanonicalJson } from "../../api/canonical";
import { useAppServices } from "../../app/context";
import { useLocale } from "../../i18n/locale";
import { ReplanningClientError } from "./client";

export function RuntimeSubmission() {
  const { runtime, dynamicReplanningClient: client } = useAppServices();
  const { locale } = useLocale();
  const zh = locale === "zh-CN";
  const [document, setDocument] = useState("");
  const [key, setKey] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  const [pending, setPending] = useState(false);
  const [unknown, setUnknown] = useState(false);
  const [feedback, setFeedback] = useState<{ ok: boolean; text: string } | null>(null);
  const inFlight = useRef(false);
  if (!client || runtime.dataPlane !== "SIMULATION" || !runtime.synthetic) return null;
  async function submit() {
    if (inFlight.current || unknown || !client) return;
    inFlight.current = true;
    setPending(true);
    setFeedback(null);
    try {
      const response = await client.submitCanonical(parseCanonicalJson(document), key);
      setFeedback({ ok: true, text: JSON.stringify(response, null, 2) });
    } catch (error) {
      const uncertain = error instanceof ReplanningClientError && error.outcomeUnknown;
      setUnknown(uncertain);
      setFeedback({ ok: false, text: `${uncertain ? "UNKNOWN_OUTCOME: " : ""}${error instanceof Error ? error.message : "CONTRACT_REJECTED"}` });
    } finally {
      inFlight.current = false;
      setPending(false);
    }
  }
  return <Card title={zh ? "提交执行事件或重排请求" : "Submit execution event or replan request"}>
    <Typography.Paragraph>{zh
      ? "提交宿主已批准的 canonical JSON。事件接收后，需由可信 Runtime 完成事实投影并准备重排请求。排队不代表计算完成。"
      : "Submit host-approved canonical JSON. After event receipt, the trusted Runtime must project facts and prepare the replan request. Queued does not mean completed."}</Typography.Paragraph>
    <label>{zh ? "事件或请求 JSON" : "Event or request JSON"}<Input.TextArea aria-label="Canonical submission" rows={6} value={document} disabled={pending || unknown} onChange={(e) => { setDocument(e.target.value); setConfirmed(false); }} /></label>
    <label>Idempotency-Key<Input aria-label="Submission idempotency key" value={key} disabled={pending || unknown} onChange={(e) => { setKey(e.target.value); setConfirmed(false); }} /></label>
    <Checkbox checked={confirmed} disabled={pending || unknown} onChange={(e) => setConfirmed(e.target.checked)}>{zh ? "确认提交至当前仿真 Runtime" : "Confirm submission to the current Simulation Runtime"}</Checkbox>
    <Button aria-label={zh ? "提交到 Runtime" : "Submit to Runtime"} onClick={() => void submit()} loading={pending} disabled={pending || unknown || !confirmed || !key.trim() || !document.trim()}>{zh ? "提交到 Runtime" : "Submit to Runtime"}</Button>
    {feedback && <Alert type={feedback.ok ? "success" : "error"} title={feedback.ok ? "Runtime acknowledgement" : "Runtime submission failed"} description={<pre data-testid="submission-result">{feedback.text}</pre>} />}
    {unknown && <Alert type="warning" title="UNKNOWN_OUTCOME" description={zh ? "结果未知。请先按原事件或请求身份查询权威状态；保留原文与幂等键，不自动重试。" : "Outcome unknown. Query authority using the original event or request identity; retain the document and key. No automatic retry."} />}
  </Card>;
}
