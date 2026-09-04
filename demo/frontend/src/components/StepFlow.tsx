import type { ScheduleState, StoryState } from "../api/types";

interface StepFlowProps {
  readonly storyState: StoryState;
  readonly scheduleState: ScheduleState | null;
}

const steps = [
  { title: "初始化工厂", detail: "固定种子与行业数据" },
  { title: "自动排产", detail: "求解与独立校验" },
  { title: "仿真基线", detail: "显式批准并发布" },
  { title: "加急重排", detail: "插单与版本比较" },
] as const;

function activeIndex(storyState: StoryState, scheduleState: ScheduleState | null) {
  if (scheduleState === "APPROVED") return 2;
  switch (storyState) {
    case "EMPTY":
      return 0;
    case "INITIALIZED":
    case "INITIAL_PLAN_RUNNING":
      return 1;
    case "READY_FOR_REVIEW":
      return 2;
    case "BASELINE_PUBLISHED":
    case "REPLAN_RUNNING":
    case "DRAFT_COMPARISON_READY":
      return 3;
  }
}

export function StepFlow({ storyState, scheduleState }: StepFlowProps) {
  const active = activeIndex(storyState, scheduleState);
  return (
    <nav className="story-steps" aria-label="演示流程">
      <ol>
        {steps.map((step, index) => {
          const status = index < active ? "complete" : index === active ? "active" : "upcoming";
          return (
            <li
              key={step.title}
              className={`story-step story-step--${status}`}
              aria-current={status === "active" ? "step" : undefined}
            >
              <span className="story-step__number" aria-hidden="true">
                {status === "complete" ? "✓" : index + 1}
              </span>
              <span>
                <strong>{step.title}</strong>
                <small>{step.detail}</small>
              </span>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
