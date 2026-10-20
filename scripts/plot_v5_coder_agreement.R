#!/usr/bin/env Rscript
# Matched human-pair comparisons; no pooling across counterpart cohorts.
library(jsonlite)
library(ggplot2)
library(grid)
args <- commandArgs(trailingOnly=TRUE)
source_path <- if(length(args)) args[[1]] else 'v5/results/dev_check_1_individual_coders/report.json'
out <- dirname(source_path)
d <- fromJSON(source_path, simplifyVector=FALSE)
stopifnot(d$analysis_policy=='sheet-main-coder-attribution-nonrepetition-v3')
rows <- list(); index <- 0L
for(lang in names(d$languages)) {
  x <- d$languages[[lang]]
  for(p in x$human_pairs) {
    for(target in c(p$left,p$right)) {
      other <- if(target==p$left) p$right else p$left
      short <- function(key) sub(' \\(main coder\\)$','',x$groups[[key]]$display)
      row_label <- paste0(short(target),' (vs ',short(other),')  ·  n=',format(p$n,big.mark=',',trim=TRUE))
      cohort <- x$groups[[target]]$counterparts[[other]]
      stopifnot(cohort$other_label$n==p$n, abs(cohort$other_label$agreement-p$agreement)<1e-12)
      index <- index+1L
      for(model in c('gemma','qwen')) {
        m <- cohort[[model]]
        stopifnot(m$n==p$n)
        rows[[length(rows)+1L]] <- data.frame(language=tools::toTitleCase(lang), target=short(target),other=short(other),
          row_id=index,row_label=row_label,n=p$n,main_pair=startsWith(p$left,'main:')&&startsWith(p$right,'main:'),
          model=tools::toTitleCase(model),agreement=m$agreement*100, baseline=p$agreement*100,
          delta=(m$agreement-p$agreement)*100,kappa=if(is.null(m$kappa)) NA_real_ else m$kappa,
          human_kappa=if(is.null(p$kappa)) NA_real_ else p$kappa)
      }
    }
  }
}
z <- do.call(rbind,rows)
z$language <- factor(z$language,levels=tools::toTitleCase(names(d$languages)))
z$model <- factor(z$model,levels=c('Gemma','Qwen'))
z$row <- factor(z$row_id,levels=rev(unique(z$row_id)))
label_map <- setNames(z$row_label,as.character(z$row_id))
colors <- c(Gemma='#0072B2',Qwen='#D55E00')
common <- function() list(
  facet_grid(language~.,scales='free_y',space='free_y',switch='y'),
  scale_y_discrete(labels=label_map),
  scale_color_manual(values=colors),scale_shape_manual(values=c(Gemma=16,Qwen=15)),
  theme_minimal(base_size=12),
  theme(panel.grid.major.y=element_line(color='#ebebeb',linewidth=.35),
        panel.grid.minor=element_blank(),panel.grid.major.x=element_line(color='#dedede',linewidth=.35),
        strip.placement='outside',strip.text.y.left=element_text(angle=0,face='bold'),
        axis.title.y=element_blank(),legend.position='top',legend.title=element_blank(),
        panel.spacing.y=unit(1.0,'lines'),plot.margin=margin(12,22,12,12),
        plot.title=element_text(face='bold',size=16),plot.subtitle=element_text(size=11),
        plot.caption=element_text(hjust=0,size=10)),
  guides(color=guide_legend(override.aes=list(size=3))))
caption <- paste('Within each row, both models and the other human use exactly the same shared records.',
 'Repetitions excluded if either human marked Yes. Points are descriptive; no uncertainty intervals.',sep='\n')
relative <- function(data) {
 ggplot(data,aes(y=row))+
  geom_vline(xintercept=0,color='#555555',linewidth=.7)+
  geom_segment(aes(x=0,xend=delta,yend=row),color='#bcbcbc',linewidth=.5,
               position=position_dodge(width=.44))+
  geom_point(aes(x=delta,color=model,shape=model),size=2.9,position=position_dodge(width=.44))+
  common()+
  scale_x_continuous(labels=function(x) ifelse(x>0,paste0('+',x),x),expand=expansion(mult=.09))+
  labs(title='Model agreement relative to human-human agreement',
       subtitle='Each row names the target human; vs identifies the other human used as the baseline.',
       x='Difference from human-human agreement (percentage points)\nLower agreement (left)                         Higher agreement (right)',caption=caption)
}
absolute <- function(data) {
 base <- unique(data[c('language','row','baseline')])
 ggplot(data,aes(y=row))+
  geom_point(data=base,aes(x=baseline),shape=18,size=3.8,color='#333333')+
  geom_point(aes(x=agreement,color=model,shape=model),size=2.9,position=position_dodge(width=.44))+
  common()+scale_x_continuous(labels=function(x)paste0(x,'%'),expand=expansion(mult=.08))+
  labs(title='Human and model agreement on the same records',
       subtitle='Black diamond: agreement between the two humans. Colored points: model agreement with the named target.',
       x='Pairwise agreement (%)',caption=caption)
}
# A single shared x scale within each figure; do not truncate individual facets independently.
plots <- list(relative_all_pairs=relative(z),absolute_all_pairs=absolute(z),
              absolute_main_pairs=absolute(z[z$main_pair,]),relative_main_pairs=relative(z[z$main_pair,]))
for(name in names(plots)) {
  height <- if(grepl('all_pairs',name)) 14.3 else 7.8
  ggsave(file.path(out,paste0(name,'.png')),plots[[name]],width=11.5,height=height,dpi=170,bg='white')
  ggsave(file.path(out,paste0(name,'.pdf')),plots[[name]],width=11.5,height=height,device='pdf')
}
# Machine-readable plotting values keep matched denominators and target direction explicit.
write_json(z,file.path(out,'plot_data.json'),pretty=TRUE,auto_unbox=TRUE,na='null')
template <- paste(readLines('scripts/templates/coder_agreement_plots.html'), collapse='\n')
page <- sub('__PLOT_DATA__', toJSON(z, auto_unbox=TRUE, na='null', digits=8), template, fixed=TRUE)
writeLines(page,file.path(out,'plots.html'))
cat('Generated four matched-cohort plots (PNG/PDF) and plots.html for',nrow(z)/2,'target-human rows.\n')
