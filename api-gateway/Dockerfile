FROM nginx:1.21-alpine

COPY nginx.conf /etc/nginx/nginx.conf
COPY dist /usr/share/nginx/html

EXPOSE 8000

CMD ["nginx", "-g", "daemon off;"] 