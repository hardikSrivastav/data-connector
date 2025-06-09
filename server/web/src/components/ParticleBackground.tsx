import React, { useEffect, useRef } from 'react';

const ParticleBackground = () => {
  const canvasRef = useRef(null);
  const animationRef = useRef(null);
  const particlesRef = useRef([]);
  const mouseRef = useRef({ x: 0, y: 0 });

  // Particle class
  class Particle {
    canvas: any;
    x: number;
    y: number;
    vx: number;
    vy: number;
    size: number;
    opacity: number;
    opacitySpeed: number;
    sizeSpeed: number;

    constructor(canvas: any) {
      this.canvas = canvas;
      this.reset();
      this.x = Math.random() * canvas.width;
      this.y = Math.random() * canvas.height;
    }

    reset() {
      this.x = Math.random() * this.canvas.width;
      this.y = Math.random() * this.canvas.height;
      this.vx = (Math.random() - 0.5) * 1.6;
      this.vy = (Math.random() - 0.5) * 1.6;
      this.size = Math.random() * 2 + 1;
      this.opacity = Math.random() * 0.4 + 0.3;
      this.opacitySpeed = (Math.random() - 0.5) * 0.02;
      this.sizeSpeed = (Math.random() - 0.5) * 0.03;
    }

    update() {
      this.x += this.vx;
      this.y += this.vy;

      // Wrap around screen
      if (this.x < 0) this.x = this.canvas.width;
      if (this.x > this.canvas.width) this.x = 0;
      if (this.y < 0) this.y = this.canvas.height;
      if (this.y > this.canvas.height) this.y = 0;

      // Animate opacity
      this.opacity += this.opacitySpeed;
      if (this.opacity <= 0.1 || this.opacity >= 0.7) {
        this.opacitySpeed *= -1;
      }

      // Animate size
      this.size += this.sizeSpeed;
      if (this.size <= 0.5 || this.size >= 3) {
        this.sizeSpeed *= -1;
      }
    }

    draw(ctx: CanvasRenderingContext2D) {
      ctx.beginPath();
      ctx.arc(this.x, this.y, this.size, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(147, 197, 253, ${this.opacity})`;
      ctx.fill();
    }

    drawLine(ctx: CanvasRenderingContext2D, particle: Particle) {
      const dx = this.x - particle.x;
      const dy = this.y - particle.y;
      const distance = Math.sqrt(dx * dx + dy * dy);
      
      if (distance < 120) {
        const opacity = (1 - distance / 120) * 0.3;
        ctx.beginPath();
        ctx.moveTo(this.x, this.y);
        ctx.lineTo(particle.x, particle.y);
        ctx.strokeStyle = `rgba(147, 197, 253, ${opacity})`;
        ctx.lineWidth = 1;
        ctx.stroke();
      }
    }

    drawMouseLine(ctx: CanvasRenderingContext2D, mouseX: number, mouseY: number) {
      const dx = this.x - mouseX;
      const dy = this.y - mouseY;
      const distance = Math.sqrt(dx * dx + dy * dy);
      
      if (distance < 150) {
        const opacity = (1 - distance / 150) * 0.6;
        ctx.beginPath();
        ctx.moveTo(this.x, this.y);
        ctx.lineTo(mouseX, mouseY);
        ctx.strokeStyle = `rgba(167, 139, 250, ${opacity})`;
        ctx.lineWidth = 1.5;
        ctx.stroke();
      }
    }
  }

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    
    const resizeCanvas = () => {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
    };

    const initParticles = () => {
      particlesRef.current = [];
      const particleCount = Math.min(80, Math.floor((canvas.width * canvas.height) / 12000));
      
      for (let i = 0; i < particleCount; i++) {
        particlesRef.current.push(new Particle(canvas));
      }
    };

    const handleMouseMove = (e) => {
      mouseRef.current.x = e.clientX;
      mouseRef.current.y = e.clientY;
    };

    const animate = () => {
      // Clear with transparent background
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      const particles = particlesRef.current;

      // Update particles
      particles.forEach(particle => {
        particle.update();
      });

      // Draw connections between particles
      for (let i = 0; i < particles.length; i++) {
        for (let j = i + 1; j < particles.length; j++) {
          particles[i].drawLine(ctx, particles[j]);
        }
      }

      // Draw connections to mouse
      particles.forEach(particle => {
        particle.drawMouseLine(ctx, mouseRef.current.x, mouseRef.current.y);
      });

      // Draw particles
      particles.forEach(particle => {
        particle.draw(ctx);
      });

      animationRef.current = requestAnimationFrame(animate);
    };

    resizeCanvas();
    initParticles();
    
    document.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('resize', () => {
      resizeCanvas();
      initParticles();
    });

    animate();

    return () => {
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current);
      }
      document.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('resize', resizeCanvas);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      className="absolute inset-0 w-full h-full"
      style={{ 
        background: 'transparent',
        pointerEvents: 'none'
      }}
    />
  );
};

export default ParticleBackground;