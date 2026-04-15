import { Component, type ReactNode, type ErrorInfo } from "react";
import { AlertTriangle, RefreshCw } from "lucide-react";

interface Props {
 children: ReactNode;
 featureName?: string;
}

interface State {
 hasError: boolean;
 error: Error | null;
}

/**
 * Granular error boundary for individual features/sections.
 * Unlike the root ErrorBoundary, this shows an inline error card
 * and allows retry without reloading the entire page.
 */
export default class FeatureErrorBoundary extends Component<Props, State> {
 state: State = { hasError: false, error: null };

 static getDerivedStateFromError(error: Error): State {
 return { hasError: true, error };
 }

 componentDidCatch(error: Error, info: ErrorInfo) {
 console.error(
 `[${this.props.featureName || "Feature"}] Error:`,
 error,
 info.componentStack
 );
 }

 handleRetry = () => {
 this.setState({ hasError: false, error: null });
 };

 render() {
 if (this.state.hasError) {
 const name = this.props.featureName || "This section";
 return (
 <div
 className="rounded-xl border border-red-200 bg-red-50 p-6 text-center" role="alert" >
 <div className="flex items-center justify-center gap-2 mb-2">
 <AlertTriangle className="w-5 h-5 text-red-500" aria-hidden="true" />
 <h3 className="text-sm font-semibold text-red-700">
 {name} encountered an error
 </h3>
 </div>
 <p className="text-xs text-red-600 mb-4">
 {this.state.error?.message || "Something went wrong."}
 </p>
 <button
 onClick={this.handleRetry}
 className="inline-flex items-center gap-1.5 px-4 py-2 text-xs font-medium text-red-700 bg-red-100 rounded-lg hover:bg-red-200 transition-colors" aria-label={`Retry loading ${name}`}
 >
 <RefreshCw className="w-3.5 h-3.5" aria-hidden="true" />
 Try Again
 </button>
 </div>
 );
 }

 return this.props.children;
 }
}
