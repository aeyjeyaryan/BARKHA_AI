import React from 'react';
import SatelliteAnalysis from '@/components/SatelliteAnalysis';

const SatelliteAnalysisPage: React.FC = () => {
  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-green-50">
      <div className="container mx-auto py-8">
        <SatelliteAnalysis />
      </div>
    </div>
  );
};

export default SatelliteAnalysisPage;