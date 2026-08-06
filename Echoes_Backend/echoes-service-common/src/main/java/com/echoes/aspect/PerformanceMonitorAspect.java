package com.echoes.aspect;

import com.echoes.annotation.Timed;
import lombok.extern.slf4j.Slf4j;
import org.aspectj.lang.ProceedingJoinPoint;
import org.aspectj.lang.annotation.Around;
import org.aspectj.lang.annotation.Aspect;
import org.aspectj.lang.annotation.Pointcut;
import org.springframework.stereotype.Component;
import org.springframework.util.StopWatch;

/**
 * 性能监控切面
 * 记录 Service 层方法执行时间
 *
 * @author echoes
 */
@Slf4j
@Aspect
@Component
public class PerformanceMonitorAspect {

    /**
     * 定义切点：拦截所有 Service 层方法
     */
    @Pointcut("execution(* com.echoes..service..*(..))")
    public void serviceMethods() {
    }

    /**
     * 定义切点：拦截标注了 @Timed 注解的方法
     */
    @Pointcut("@annotation(com.echoes.annotation.Timed)")
    public void timedMethods() {
    }

    /**
     * 围绕通知：记录方法执行时间（Service 层）
     *
     * @param joinPoint 切点
     * @return 方法执行结果
     * @throws Throwable 异常
     */
    @Around("serviceMethods()")
    public Object monitorExecutionTime(ProceedingJoinPoint joinPoint) throws Throwable {
        String className = joinPoint.getSignature().getDeclaringTypeName();
        String methodName = joinPoint.getSignature().getName();
        String fullName = className + "." + methodName;

        StopWatch stopWatch = new StopWatch(fullName);
        stopWatch.start();

        try {
            Object result = joinPoint.proceed();
            return result;
        } catch (Throwable e) {
            log.error("方法执行异常：{}", fullName, e);
            throw e;
        } finally {
            stopWatch.stop();
            long totalTimeMillis = stopWatch.getTotalTimeMillis();

            // 执行时间超过 1 秒的方法记录警告日志
            if (totalTimeMillis > 1000) {
                log.warn("方法执行缓慢：{}, 耗时：{}ms", fullName, totalTimeMillis);
            } else {
                log.debug("方法执行完成：{}, 耗时：{}ms", fullName, totalTimeMillis);
            }
        }
    }

    /**
     * 围绕通知：记录标注 @Timed 注解的方法执行时间
     *
     * @param joinPoint 切点
     * @param timed 注解实例
     * @return 方法执行结果
     * @throws Throwable 异常
     */
    @Around("timedMethods() && @annotation(timed)")
    public Object monitorTimedMethod(ProceedingJoinPoint joinPoint, Timed timed) throws Throwable {
        String className = joinPoint.getSignature().getDeclaringTypeName();
        String methodName = joinPoint.getSignature().getName();
        String fullName = className + "." + methodName;
        String description = timed.description();

        StopWatch stopWatch = new StopWatch(fullName);
        stopWatch.start();

        try {
            if (timed.logParams()) {
                log.info("开始执行：{} - {}, 参数：{}", fullName, description, java.util.Arrays.toString(joinPoint.getArgs()));
            } else {
                log.info("开始执行：{} - {}", fullName, description);
            }
            Object result = joinPoint.proceed();
            return result;
        } catch (Throwable e) {
            log.error("方法执行异常：{} - {}", fullName, description, e);
            throw e;
        } finally {
            stopWatch.stop();
            long totalTimeMillis = stopWatch.getTotalTimeMillis();
            long warnThreshold = timed.warnThreshold();

            if (totalTimeMillis > warnThreshold) {
                log.warn("方法执行缓慢：{} - {}, 耗时：{}ms (阈值：{}ms)", fullName, description, totalTimeMillis, warnThreshold);
            } else {
                log.info("方法执行完成：{} - {}, 耗时：{}ms", fullName, description, totalTimeMillis);
            }
        }
    }
}
