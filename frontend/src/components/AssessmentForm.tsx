import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Form, FormControl, FormDescription, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { MapPin, Home, Droplets, Gauge, Loader2 } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { api, SiteDetailsInput, ROOF_MATERIALS, ROOF_CONDITIONS, SOIL_TYPES } from "@/lib/api";

const assessmentSchema = z.object({
  site_name: z.string().min(2, "Site name must be at least 2 characters"),
  latitude: z.number().min(-90).max(90),
  longitude: z.number().min(-180).max(180),
  roof_area: z.number().min(1, "Roof area must be positive"),
  roof_material: z.enum(ROOF_MATERIALS),
  roof_condition: z.enum(ROOF_CONDITIONS),
  soil_type: z.enum(SOIL_TYPES),
  annual_rainfall: z.number().min(0, "Rainfall cannot be negative"),
  water_demand: z.number().min(1, "Water demand must be positive"),
});

type AssessmentFormData = z.infer<typeof assessmentSchema>;

interface AssessmentFormProps {
  onSuccess?: (result: any) => void;
}

export const AssessmentForm = ({ onSuccess }: AssessmentFormProps) => {
  const [isLoading, setIsLoading] = useState(false);
  const { toast } = useToast();

  const form = useForm<AssessmentFormData>({
    resolver: zodResolver(assessmentSchema),
    defaultValues: {
      site_name: "",
      latitude: 0,
      longitude: 0,
      roof_area: 0,
      roof_material: "concrete",
      roof_condition: "good",
      soil_type: "loamy",
      annual_rainfall: 0,
      water_demand: 0,
    },
  });

  const onSubmit = async (data: AssessmentFormData) => {
    setIsLoading(true);
    
    try {
      const siteData: SiteDetailsInput = {
        site_name: data.site_name,
        latitude: data.latitude,
        longitude: data.longitude,
        roof_area: data.roof_area,
        roof_material: data.roof_material,
        roof_condition: data.roof_condition,
        soil_type: data.soil_type,
        annual_rainfall: data.annual_rainfall,
        water_demand: data.water_demand,
      };
      
      const result = await api.createAssessment(siteData);
      
      toast({
        title: "Assessment Complete!",
        description: "Your rainwater harvesting assessment has been generated successfully.",
      });

      onSuccess?.(result);
      form.reset();
    } catch (error) {
      console.error('Assessment failed:', error);
      toast({
        title: "Assessment Failed",
        description: "There was an error processing your assessment. Please try again.",
        variant: "destructive",
      });
    } finally {
      setIsLoading(false);
    }
  };

  const getCurrentLocation = () => {
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        (position) => {
          form.setValue("latitude", position.coords.latitude);
          form.setValue("longitude", position.coords.longitude);
          toast({
            title: "Location Updated",
            description: "Your current location has been set.",
          });
        },
        (error) => {
          toast({
            title: "Location Error",
            description: "Could not get your location. Please enter manually.",
            variant: "destructive",
          });
        }
      );
    } else {
      toast({
        title: "Location Not Supported",
        description: "Geolocation is not supported by your browser.",
        variant: "destructive",
      });
    }
  };

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <Card className="glass-card border-border/50">
        <CardHeader>
          <CardTitle className="flex items-center space-x-2">
            <Droplets className="h-6 w-6 text-primary" />
            <span>Rainwater Harvesting Assessment</span>
          </CardTitle>
          <CardDescription>
            Fill in the details below to get a comprehensive feasibility analysis for your site
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Form {...form}>
            <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
              
              {/* Site Information */}
              <div className="space-y-4">
                <div className="flex items-center space-x-2 text-lg font-semibold">
                  <Home className="h-5 w-5 text-accent" />
                  <span>Site Information</span>
                </div>

                <FormField
                  control={form.control}
                  name="site_name"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Site Name</FormLabel>
                      <FormControl>
                        <Input placeholder="e.g., Residential Building, Office Complex" {...field} />
                      </FormControl>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <FormField
                    control={form.control}
                    name="latitude"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Latitude</FormLabel>
                        <FormControl>
                          <Input 
                            type="number" 
                            step="any"
                            placeholder="12.9716" 
                            {...field}
                            onChange={(e) => field.onChange(parseFloat(e.target.value) || 0)}
                          />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <FormField
                    control={form.control}
                    name="longitude"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Longitude</FormLabel>
                        <FormControl>
                          <Input 
                            type="number" 
                            step="any"
                            placeholder="77.5946" 
                            {...field}
                            onChange={(e) => field.onChange(parseFloat(e.target.value) || 0)}
                          />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </div>

                <Button 
                  type="button" 
                  variant="outline" 
                  size="sm"
                  onClick={getCurrentLocation}
                  className="w-fit"
                >
                  <MapPin className="h-4 w-4 mr-2" />
                  Use Current Location
                </Button>
              </div>

              {/* Roof Details */}
              <div className="space-y-4">
                <div className="flex items-center space-x-2 text-lg font-semibold">
                  <Home className="h-5 w-5 text-accent" />
                  <span>Roof Details</span>
                </div>

                <FormField
                  control={form.control}
                  name="roof_area"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Roof Area (m²)</FormLabel>
                      <FormControl>
                        <Input 
                          type="number" 
                          placeholder="150" 
                          {...field}
                          onChange={(e) => field.onChange(parseFloat(e.target.value) || 0)}
                        />
                      </FormControl>
                      <FormDescription>
                        Total catchment area of the roof in square meters
                      </FormDescription>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <FormField
                    control={form.control}
                    name="roof_material"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Roof Material</FormLabel>
                        <Select onValueChange={field.onChange} defaultValue={field.value}>
                          <FormControl>
                            <SelectTrigger>
                              <SelectValue placeholder="Select roof material" />
                            </SelectTrigger>
                          </FormControl>
                          <SelectContent>
                            <SelectItem value="concrete">Concrete</SelectItem>
                            <SelectItem value="tile">Tile</SelectItem>
                            <SelectItem value="metal">Metal Sheet</SelectItem>
                            <SelectItem value="asbestos">Asbestos</SelectItem>
                            <SelectItem value="thatched">Thatched</SelectItem>
                          </SelectContent>
                        </Select>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <FormField
                    control={form.control}
                    name="roof_condition"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Roof Condition</FormLabel>
                        <Select onValueChange={field.onChange} defaultValue={field.value}>
                          <FormControl>
                            <SelectTrigger>
                              <SelectValue placeholder="Select condition" />
                            </SelectTrigger>
                          </FormControl>
                          <SelectContent>
                            <SelectItem value="good">Good</SelectItem>
                            <SelectItem value="fair">Fair</SelectItem>
                            <SelectItem value="poor">Poor</SelectItem>
                          </SelectContent>
                        </Select>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </div>
              </div>

              {/* Site Conditions */}
              <div className="space-y-4">
                <div className="flex items-center space-x-2 text-lg font-semibold">
                  <Gauge className="h-5 w-5 text-accent" />
                  <span>Site Conditions</span>
                </div>

                <FormField
                  control={form.control}
                  name="soil_type"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Soil Type</FormLabel>
                      <Select onValueChange={field.onChange} defaultValue={field.value}>
                        <FormControl>
                          <SelectTrigger>
                            <SelectValue placeholder="Select soil type" />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          <SelectItem value="sandy">Sandy</SelectItem>
                          <SelectItem value="loamy">Loamy</SelectItem>
                          <SelectItem value="clay">Clay</SelectItem>
                          <SelectItem value="rocky">Rocky</SelectItem>
                        </SelectContent>
                      </Select>
                      <FormDescription>
                        Soil type affects groundwater recharge feasibility
                      </FormDescription>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <FormField
                  control={form.control}
                  name="annual_rainfall"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Annual Rainfall (mm)</FormLabel>
                      <FormControl>
                        <Input 
                          type="number" 
                          placeholder="1200" 
                          {...field}
                          onChange={(e) => field.onChange(parseFloat(e.target.value) || 0)}
                        />
                      </FormControl>
                      <FormDescription>
                        Average annual rainfall in millimeters for your area
                      </FormDescription>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <FormField
                  control={form.control}
                  name="water_demand"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Daily Water Demand (L/day)</FormLabel>
                      <FormControl>
                        <Input 
                          type="number" 
                          placeholder="500" 
                          {...field}
                          onChange={(e) => field.onChange(parseFloat(e.target.value) || 0)}
                        />
                      </FormControl>
                      <FormDescription>
                        Average daily water consumption in liters
                      </FormDescription>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>

              {/* Submit Button */}
              <Button 
                type="submit" 
                size="lg" 
                variant="ocean" 
                className="w-full" 
                disabled={isLoading}
              >
                {isLoading ? (
                  <>
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    Generating Assessment...
                  </>
                ) : (
                  <>
                    <Droplets className="h-4 w-4 mr-2" />
                    Generate Assessment
                  </>
                )}
              </Button>
            </form>
          </Form>
        </CardContent>
      </Card>
    </div>
  );
};