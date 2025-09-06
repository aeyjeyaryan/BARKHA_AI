import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { 
  Droplets, 
  TrendingUp, 
  AlertTriangle, 
  Download, 
  RotateCcw,
  Home,
  Calculator,
  FileText,
  CheckCircle,
  XCircle,
  AlertCircle
} from "lucide-react";
import { AssessmentResult as AssessmentResultType, formatCurrency, formatVolume, RECOMMENDATION_LABELS } from "@/lib/api";

interface AssessmentResultProps {
  result: AssessmentResultType;
  onNewAssessment: () => void;
}

export const AssessmentResult = ({ result, onNewAssessment }: AssessmentResultProps) => {
  const getRecommendationColor = (recommendation: string) => {
    switch (recommendation) {
      case 'hybrid':
      case 'storage_priority_hybrid':
        return 'success';
      case 'storage_only':
      case 'recharge_only':
        return 'warning';
      case 'not_feasible':
        return 'destructive';
      default:
        return 'secondary';
    }
  };

  const getRecommendationIcon = (recommendation: string) => {
    switch (recommendation) {
      case 'hybrid':
      case 'storage_priority_hybrid':
      case 'storage_only':
      case 'recharge_only':
        return CheckCircle;
      case 'not_feasible':
        return XCircle;
      default:
        return AlertCircle;
    }
  };

  const RecommendationIcon = getRecommendationIcon(result.recommended_option);

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="space-y-2">
          <h1 className="text-3xl lg:text-4xl font-bold">
            Assessment <span className="gradient-text">Results</span>
          </h1>
          <p className="text-muted-foreground">
            Comprehensive analysis for rainwater harvesting feasibility
          </p>
        </div>
        
        <div className="flex space-x-2">
          <Button variant="outline" onClick={onNewAssessment}>
            <RotateCcw className="h-4 w-4 mr-2" />
            New Assessment
          </Button>
          <Button variant="ocean">
            <Download className="h-4 w-4 mr-2" />
            Download Report
          </Button>
        </div>
      </div>

      {/* Quick Stats */}
      <div className="grid md:grid-cols-3 gap-6">
        <Card className="glass-card">
          <CardContent className="p-6">
            <div className="flex items-center space-x-3">
              <div className="h-12 w-12 rounded-lg bg-primary/10 flex items-center justify-center">
                <Droplets className="h-6 w-6 text-primary" />
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Harvestable Volume</p>
                <p className="text-2xl font-bold">{formatVolume(result.harvestable_volume)}</p>
                <p className="text-xs text-success">per year</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="glass-card">
          <CardContent className="p-6">
            <div className="flex items-center space-x-3">
              <div className="h-12 w-12 rounded-lg bg-accent/10 flex items-center justify-center">
                <TrendingUp className="h-6 w-6 text-accent" />
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Annual Savings</p>
                <p className="text-2xl font-bold">{formatCurrency(result.savings_analysis.annual_cost_savings)}</p>
                <p className="text-xs text-success">cost reduction</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="glass-card">
          <CardContent className="p-6">
            <div className="flex items-center space-x-3">
              <div className="h-12 w-12 rounded-lg bg-warning/10 flex items-center justify-center">
                <Calculator className="h-6 w-6 text-warning" />
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Implementation Cost</p>
                <p className="text-2xl font-bold">{formatCurrency(result.cost_analysis.total_cost)}</p>
                <p className="text-xs text-muted-foreground">one-time investment</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Recommendation */}
      <Card className="glass-card border-border/50">
        <CardHeader>
          <CardTitle className="flex items-center space-x-2">
            <RecommendationIcon className="h-6 w-6 text-primary" />
            <span>Recommendation</span>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center space-x-4">
            <Badge 
              variant={getRecommendationColor(result.recommended_option)} 
              className="text-sm px-4 py-2"
            >
              {RECOMMENDATION_LABELS[result.recommended_option as keyof typeof RECOMMENDATION_LABELS] || result.recommended_option}
            </Badge>
            <p className="text-muted-foreground">
              Based on your site conditions and requirements
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Detailed Analysis */}
      <Tabs defaultValue="technical" className="space-y-6">
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="technical">Technical Details</TabsTrigger>
          <TabsTrigger value="costs">Cost Analysis</TabsTrigger>
          <TabsTrigger value="boq">Bill of Quantities</TabsTrigger>
          <TabsTrigger value="safety">Safety Checks</TabsTrigger>
        </TabsList>

        <TabsContent value="technical" className="space-y-6">
          <div className="grid md:grid-cols-2 gap-6">
            {/* Storage Requirements */}
            <Card className="glass-card">
              <CardHeader>
                <CardTitle className="flex items-center space-x-2">
                  <Home className="h-5 w-5 text-primary" />
                  <span>Storage System</span>
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <div className="flex justify-between">
                    <span className="text-sm text-muted-foreground">Required Volume</span>
                    <span className="font-medium">{formatVolume(result.storage_recommendation.required_volume)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-sm text-muted-foreground">Recommended Volume</span>
                    <span className="font-medium">{formatVolume(result.storage_recommendation.recommended_volume)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-sm text-muted-foreground">Storage Duration</span>
                    <span className="font-medium">{result.storage_recommendation.storage_days} days</span>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Recharge System */}
            <Card className="glass-card">
              <CardHeader>
                <CardTitle className="flex items-center space-x-2">
                  <Droplets className="h-5 w-5 text-accent" />
                  <span>Recharge System</span>
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="space-y-2">
                  <div className="flex justify-between">
                    <span className="text-sm text-muted-foreground">Pit Diameter</span>
                    <span className="font-medium">{result.recharge_recommendation.recharge_pit.diameter}m</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-sm text-muted-foreground">Pit Depth</span>
                    <span className="font-medium">{result.recharge_recommendation.recharge_pit.depth}m</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-sm text-muted-foreground">Suitability Score</span>
                    <span className="font-medium">{result.recharge_recommendation.suitability_score}/10</span>
                  </div>
                </div>
                <Progress value={result.recharge_recommendation.suitability_score * 10} className="h-2" />
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="costs" className="space-y-6">
          <Card className="glass-card">
            <CardHeader>
              <CardTitle>Cost Breakdown</CardTitle>
              <CardDescription>Detailed implementation and operational costs</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {Object.entries(result.cost_analysis).map(([key, value]) => (
                  key !== 'total_cost' && (
                    <div key={key} className="flex justify-between items-center py-2 border-b border-border/30">
                      <span className="text-sm text-muted-foreground capitalize">
                        {key.replace(/_/g, ' ')}
                      </span>
                      <span className="font-medium">{formatCurrency(value as number)}</span>
                    </div>
                  )
                ))}
                <div className="flex justify-between items-center py-3 border-t-2 border-primary/20">
                  <span className="text-lg font-semibold">Total Cost</span>
                  <span className="text-lg font-bold text-primary">{formatCurrency(result.cost_analysis.total_cost)}</span>
                </div>
              </div>

              <div className="mt-6 p-4 bg-muted/30 rounded-lg">
                <h4 className="font-medium mb-2">Savings Analysis</h4>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span>Monthly Savings</span>
                    <span className="font-medium text-success">{formatCurrency(result.savings_analysis.monthly_savings)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Payback Period</span>
                    <span className="font-medium">
                      {Math.ceil(result.cost_analysis.total_cost / result.savings_analysis.annual_cost_savings)} years
                    </span>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="boq" className="space-y-6">
          <Card className="glass-card">
            <CardHeader>
              <CardTitle className="flex items-center space-x-2">
                <FileText className="h-5 w-5 text-primary" />
                <span>Bill of Quantities</span>
              </CardTitle>
              <CardDescription>Detailed material and labor requirements</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-border/50">
                      <th className="text-left p-2 text-sm font-medium text-muted-foreground">Item</th>
                      <th className="text-right p-2 text-sm font-medium text-muted-foreground">Quantity</th>
                      <th className="text-right p-2 text-sm font-medium text-muted-foreground">Rate</th>
                      <th className="text-right p-2 text-sm font-medium text-muted-foreground">Amount</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.bill_of_quantities.items.map((item, index) => (
                      <tr key={index} className="border-b border-border/30">
                        <td className="p-2 text-sm">{item.item}</td>
                        <td className="p-2 text-sm text-right">{item.quantity}</td>
                        <td className="p-2 text-sm text-right">{formatCurrency(item.rate)}</td>
                        <td className="p-2 text-sm text-right font-medium">{formatCurrency(item.amount)}</td>
                      </tr>
                    ))}
                    <tr className="border-t-2 border-primary/20">
                      <td colSpan={3} className="p-2 text-right font-semibold">Total</td>
                      <td className="p-2 text-right font-bold text-primary">{formatCurrency(result.bill_of_quantities.total_cost)}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="safety" className="space-y-6">
          <Card className="glass-card">
            <CardHeader>
              <CardTitle className="flex items-center space-x-2">
                <AlertTriangle className="h-5 w-5 text-warning" />
                <span>Safety & Compliance</span>
              </CardTitle>
              <CardDescription>Important considerations and requirements</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {result.safety_checks.map((check, index) => (
                  <div key={index} className={`p-3 rounded-lg border-l-4 ${
                    check.includes('CRITICAL') 
                      ? 'bg-destructive/10 border-destructive' 
                      : check.includes('WARNING')
                      ? 'bg-warning/10 border-warning'
                      : 'bg-primary/10 border-primary'
                  }`}>
                    <p className="text-sm">{check}</p>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
};