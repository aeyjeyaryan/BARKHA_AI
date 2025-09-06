import { Header } from "@/components/Header";
import { Hero } from "@/components/Hero";

const Dashboard = () => {
  return (
    <div className="min-h-screen bg-background">
      <Header />
      <main>
        <Hero />
      </main>
    </div>
  );
};

export default Dashboard;