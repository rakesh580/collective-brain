import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { LogoIcon } from "../layout/Logo";
import {
  Users, Upload, MessageSquare, CheckCircle, ArrowRight, X,
} from "lucide-react";

interface Props {
  onDismiss: () => void;
}

const steps = [
  {
    id: "members",
    title: "Add Team Members",
    description: "Start by adding people to your team. You can add them manually or discover them through data ingestion.",
    icon: Users,
    action: "/members",
    actionLabel: "Add Members",
    color: "from-indigo-500 to-violet-500",
  },
  {
    id: "ingest",
    title: "Ingest Knowledge",
    description: "Feed your team's Git repos, documents, Slack exports, or markdown files into the Collective Brain.",
    icon: Upload,
    action: "/ingest",
    actionLabel: "Ingest Data",
    color: "from-emerald-500 to-teal-500",
  },
  {
    id: "chat",
    title: "Ask the AI",
    description: "Chat with the Collective Brain to find experts, discover patterns, and get team insights.",
    icon: MessageSquare,
    action: "/chat",
    actionLabel: "Start Chat",
    color: "from-amber-500 to-orange-500",
  },
];

export default function OnboardingWizard({ onDismiss }: Props) {
  const [currentStep, setCurrentStep] = useState(0);
  const navigate = useNavigate();

  const step = steps[currentStep];
  const Icon = step.icon;
  const isLast = currentStep === steps.length - 1;

  return (
    <div className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-2xl p-6 mb-6 shadow-sm relative overflow-hidden">
      {/* Background decoration */}
      <div className="absolute top-0 right-0 w-64 h-64 bg-gradient-to-bl from-indigo-500/5 to-transparent rounded-bl-full" />

      {/* Dismiss */}
      <button
        onClick={onDismiss}
        className="absolute top-3 right-3 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 transition-colors z-10"
        aria-label="Dismiss onboarding wizard"
      >
        <X size={16} />
      </button>

      {/* Header */}
      <div className="flex items-center gap-3 mb-5">
        <LogoIcon size={28} />
        <div>
          <h3 className="text-sm font-semibold text-slate-800 dark:text-slate-200">
            Getting Started
          </h3>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            Step {currentStep + 1} of {steps.length}
          </p>
        </div>
      </div>

      {/* Progress bar */}
      <div className="flex gap-1.5 mb-5">
        {steps.map((s, i) => (
          <div
            key={s.id}
            className={`h-1 flex-1 rounded-full transition-all duration-300 ${
              i <= currentStep
                ? "bg-gradient-to-r from-indigo-500 to-violet-500"
                : "bg-slate-200 dark:bg-slate-700"
            }`}
          />
        ))}
      </div>

      {/* Step content */}
      <div className="flex items-start gap-4">
        <div className={`p-3 rounded-xl bg-gradient-to-br ${step.color} shadow-lg`}>
          <Icon size={24} className="text-white" />
        </div>
        <div className="flex-1">
          <h4 className="text-base font-semibold text-slate-800 dark:text-white mb-1">
            {step.title}
          </h4>
          <p className="text-sm text-slate-600 dark:text-slate-400 mb-4">
            {step.description}
          </p>

          <div className="flex items-center gap-3">
            <button
              onClick={() => {
                navigate(step.action);
                onDismiss();
              }}
              className={`flex items-center gap-2 px-4 py-2 bg-gradient-to-r ${step.color} text-white text-sm font-medium rounded-lg hover:shadow-lg hover:opacity-90 transition-all btn-press`}
            >
              {step.actionLabel}
              <ArrowRight size={14} />
            </button>

            {!isLast ? (
              <button
                onClick={() => setCurrentStep((s) => s + 1)}
                className="text-sm text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 transition-colors"
              >
                Skip this step
              </button>
            ) : (
              <button
                onClick={onDismiss}
                className="flex items-center gap-1.5 text-sm text-emerald-600 dark:text-emerald-400 font-medium hover:text-emerald-700 dark:hover:text-emerald-300 transition-colors"
              >
                <CheckCircle size={14} />
                All done!
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Step indicators */}
      <div className="flex justify-center gap-4 mt-5 pt-4 border-t border-slate-100 dark:border-slate-700">
        {steps.map((s, i) => {
          const StepIcon = s.icon;
          return (
            <button
              key={s.id}
              onClick={() => setCurrentStep(i)}
              className={`flex items-center gap-1.5 text-xs transition-all ${
                i === currentStep
                  ? "text-indigo-600 dark:text-indigo-400 font-medium"
                  : i < currentStep
                  ? "text-emerald-500"
                  : "text-slate-400"
              }`}
            >
              {i < currentStep ? (
                <CheckCircle size={14} />
              ) : (
                <StepIcon size={14} />
              )}
              {s.title}
            </button>
          );
        })}
      </div>
    </div>
  );
}
