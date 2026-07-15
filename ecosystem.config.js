module.exports = {
  apps: [
    {
      name: 'ai-orchestration-api',
      script: './scripts/start-prod.sh',
      interpreter: 'bash',
      cwd: '/home/tsiky-ny-antsa/Project/AI-Orchestration-API',
      env: {
        NODE_ENV: 'production',
        APP_ENV: 'production',
        HOST: '0.0.0.0',
        PORT: 8080,
        WORKERS: 2
      },
      instances: 1,
      exec_mode: 'fork',
      autorestart: true,
      watch: false,
      max_memory_restart: '1G',
      log_file: './server.log',
      error_file: './server.log',
      out_file: './server.log',
      merge_logs: true
    }
  ]
};
