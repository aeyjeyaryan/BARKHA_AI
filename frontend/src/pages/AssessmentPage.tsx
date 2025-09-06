import { useState } from "react";
import { Header } from "@/components/Header";
import { AssessmentForm } from "@/components/AssessmentForm";
import { AssessmentResult } from "@/components/AssessmentResult";
import { AssessmentResult as AssessmentResultType } from "@/lib/api";

const AssessmentPage = () => {
  const [result, setResult] = useState<AssessmentResultType | null>(null);

  const handleAssessmentSuccess = (assessmentResult: AssessmentResultType) => {
    setResult(assessmentResult);
  };

  const handleNewAssessment = () => {
    setResult(null);
  };

  return (
    <div className="min-h-screen bg-background">
      <Header />
      
      <main className="container mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {result ? (
          <AssessmentResult result={result} onNewAssessment={handleNewAssessment} />
        ) : (
          <div className="space-y-8">
            <div className="text-center space-y-4">
              <h1 className="text-3xl lg:text-4xl font-bold">
                Start Your <span className="gradient-text">Assessment</span>
              </h1>
              <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
                Get a comprehensive rainwater harvesting feasibility analysis for your property. 
                Our AI-powered assessment provides detailed recommendations and cost analysis.
              </p>
            </div>
            
            <AssessmentForm onSuccess={handleAssessmentSuccess} />
          </div>
        )}
      </main>
    </div>
  );
};

export default AssessmentPage;