interface StatCardProps {
  title: string
  value: string | number
  subtitle?: string
  trend?: 'up' | 'down' | 'neutral'
  color?: 'green' | 'red' | 'yellow' | 'blue' | 'purple' | 'default'
  icon?: string
}

export default function StatCard({
  title,
  value,
  subtitle,
  trend,
  color = 'default',
  icon
}: StatCardProps) {
  const colorClasses = {
    green: 'text-emerald-400',
    red: 'text-red-400',
    yellow: 'text-yellow-400',
    blue: 'text-blue-400',
    purple: 'text-purple-400',
    default: 'text-white'
  }

  const trendIcon = trend === 'up' ? '▲' : trend === 'down' ? '▼' : '●'
  const trendColor = trend === 'up' 
    ? 'text-emerald-400' 
    : trend === 'down' 
    ? 'text-red-400' 
    : 'text-gray-400'

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 
                    hover:border-gray-700 transition-all duration-200 animate-fade-in">
      <div className="flex items-start justify-between mb-2">
        <p className="text-gray-400 text-sm font-medium">{title}</p>
        {icon && <span className="text-xl">{icon}</span>}
      </div>
      
      <div className={`text-2xl font-bold mb-1 ${colorClasses[color]}`}>
        {value}
      </div>
      
      {subtitle && (
        <p className="text-gray-500 text-xs flex items-center gap-1">
          {trend && (
            <span className={trendColor}>{trendIcon}</span>
          )}
          {subtitle}
        </p>
      )}
    </div>
  )
}