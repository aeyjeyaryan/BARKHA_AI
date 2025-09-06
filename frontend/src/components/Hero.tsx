import { Button } from "@/components/ui/button";
import { ArrowRight, Droplets, Calculator, FileText, Zap } from "lucide-react";
import { Link } from "react-router-dom";
import heroImage from "@/assets/hero-rainwater.jpg";

export const Hero = () => {
  const features = [
    {
      icon: Calculator,
      title: "Smart Assessment",
      description: "AI-powered calculations for optimal rainwater harvesting"
    },
    {
      icon: FileText,
      title: "Detailed Reports", 
      description: "Professional PDF reports with cost analysis & BOQ"
    },
    {
      icon: Zap,
      title: "Instant Results",
      description: "Get feasibility analysis in minutes, not days"
    }
  ];

  return (
    <section className="relative overflow-hidden bg-gradient-water">
      {/* Background Pattern */}
      <div className="absolute inset-0 bg-grid-pattern opacity-5" />
      
      {/* Hero Content */}
      <div className="relative container mx-auto px-4 sm:px-6 lg:px-8 py-20 lg:py-32">
        <div className="grid lg:grid-cols-2 gap-12 items-center">
          {/* Left Column - Content */}
          <div className="space-y-8">
            <div className="space-y-4">
              <div className="inline-flex items-center space-x-2 bg-primary/10 text-primary px-4 py-2 rounded-full text-sm font-medium">
                <Droplets className="h-4 w-4 animate-float" />
                <span>Professional Water Assessment Platform</span>
              </div>
              
              <h1 className="text-4xl lg:text-6xl font-bold leading-tight">
                <span className="gradient-text">Intelligent</span><br />
                Rainwater Harvesting<br />
                <span className="text-foreground">Assessment</span>
              </h1>
              
              <p className="text-lg text-muted-foreground max-w-lg">
                Transform rooftops into sustainable water sources. Get professional 
                feasibility reports, cost analysis, and implementation guidance in minutes.
              </p>
            </div>

            {/* CTA Buttons */}
            <div className="flex flex-col sm:flex-row gap-4">
              <Button size="xl" variant="ocean" asChild>
                <Link to="/assess" className="group">
                  Start Free Assessment
                  <ArrowRight className="h-5 w-5 group-hover:translate-x-1 transition-transform" />
                </Link>
              </Button>
              
              <Button size="xl" variant="outline" asChild>
                <Link to="/demo">
                  View Demo Report
                </Link>
              </Button>
            </div>

            {/* Stats */}
            <div className="grid grid-cols-3 gap-6 pt-8 border-t border-border/50">
              <div className="text-center">
                <div className="text-2xl font-bold text-primary">500+</div>
                <div className="text-sm text-muted-foreground">Assessments</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-accent">₹2.5L+</div>
                <div className="text-sm text-muted-foreground">Savings Projected</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-success">10M+</div>
                <div className="text-sm text-muted-foreground">Liters Harvested</div>
              </div>
            </div>
          </div>

          {/* Right Column - Image */}
          <div className="relative">
            <div className="relative rounded-2xl overflow-hidden shadow-water">
              <img 
                src={heroImage} 
                alt="Rainwater harvesting system on modern rooftop"
                className="w-full h-full object-cover aspect-[4/3]"
              />
              <div className="absolute inset-0 bg-gradient-to-tr from-primary/20 to-transparent" />
            </div>
            
            {/* Floating Card */}
            <div className="absolute -bottom-6 -left-6 glass-card p-6 rounded-xl">
              <div className="flex items-center space-x-3">
                <div className="h-12 w-12 rounded-full bg-success/20 flex items-center justify-center">
                  <Droplets className="h-6 w-6 text-success animate-float" />
                </div>
                <div>
                  <div className="font-semibold">15,000L</div>
                  <div className="text-sm text-muted-foreground">Annual Harvest Potential</div>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Feature Cards */}
        <div className="grid md:grid-cols-3 gap-6 mt-20">
          {features.map((feature, index) => {
            const Icon = feature.icon;
            return (
              <div key={index} className="glass-card p-6 rounded-xl hover:scale-105 transition-transform duration-300">
                <div className="h-12 w-12 rounded-lg bg-primary/10 flex items-center justify-center mb-4">
                  <Icon className="h-6 w-6 text-primary" />
                </div>
                <h3 className="font-semibold mb-2">{feature.title}</h3>
                <p className="text-sm text-muted-foreground">{feature.description}</p>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
};