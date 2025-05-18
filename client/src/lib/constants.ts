export const siteConfig = {
  name: "Ceneca",
  description: "On-premise AI data-analysis that connects directly to your databases.",
  url: "https://ceneca.ai",
  ogImage: "/og.png",
  links: {
    twitter: "https://twitter.com/ceneca",
    github: "https://github.com/hardikSrivastav/data-connector",
    linkedin: "https://linkedin.com/company/ceneca",
  },
}

export const features = [
  {
    title: "Natural Language Queries",
    description: "Ask questions in plain English to query your databases. No SQL knowledge required.",
    icon: "MessageSquare",
  },
  {
    title: "Multiple Database Support",
    description: "Connect to MongoDB, PostgreSQL, Qdrant, and more database systems.",
    icon: "Database",
  },
  {
    title: "On-Premise Security",
    description: "Data never leaves your security perimeter. All processing happens locally.",
    icon: "Shield",
  },
  {
    title: "AI-Powered Insights",
    description: "Get intelligent analysis and visualizations of your data.",
    icon: "LineChart",
  },
]

export const databases = [
  { name: "MongoDB", logo: "/images/mongodb.svg" },
  { name: "PostgreSQL", logo: "/images/postgresql.svg" },
  { name: "Qdrant", logo: "/images/qdrant.svg" },
  { name: "MySQL", logo: "/images/mysql.svg" },
  { name: "Elasticsearch", logo: "/images/elasticsearch.svg" },
  { name: "Redis", logo: "/images/redis.svg" },
]

export const cliCommands = [
  { 
    command: "ceneca connect --db mongodb://localhost:27017/mydb", 
    description: "Connect to your MongoDB database" 
  },
  { 
    command: "ceneca query \"Show me sales by region for the last quarter\"", 
    description: "Query your data with natural language" 
  },
  { 
    command: "ceneca analyze \"What are the key trends in our customer data?\"", 
    description: "Get AI-powered insights from your data" 
  },
] 