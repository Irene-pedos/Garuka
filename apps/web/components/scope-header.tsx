import { Clock, Globe, School, MapPin } from "lucide-react";
import { Badge } from "@/components/ui/badge";

interface ScopeHeaderProps {
  title: string;
  description?: string;
  scope?: {
    level: string;
    name: string;
  };
  dateInfo?: string;
  children?: React.ReactNode;
}

export function ScopeHeader({
  title,
  description,
  scope,
  dateInfo,
  children,
}: ScopeHeaderProps) {
  const getScopeIcon = (level?: string) => {
    switch (level) {
      case "national":
        return <Globe className="h-3.5 w-3.5 mr-1" />;
      case "district":
      case "sector":
        return <MapPin className="h-3.5 w-3.5 mr-1" />;
      case "school":
        return <School className="h-3.5 w-3.5 mr-1" />;
      default:
        return null;
    }
  };

  return (
    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2 border-b">
      <div>
        <div className="flex flex-wrap items-center gap-2">
          <h1 className="text-2xl font-bold tracking-tight text-foreground">{title}</h1>
          {scope && (
            <Badge variant="secondary" className="capitalize text-xs font-medium">
              {getScopeIcon(scope.level)}
              {scope.name} ({scope.level})
            </Badge>
          )}
          {dateInfo && (
            <Badge variant="outline" className="text-xs font-normal text-muted-foreground">
              {dateInfo}
            </Badge>
          )}
        </div>
        {description && (
          <p className="text-sm text-muted-foreground mt-1">{description}</p>
        )}
      </div>

      {children && <div className="flex items-center gap-2">{children}</div>}
    </div>
  );
}
