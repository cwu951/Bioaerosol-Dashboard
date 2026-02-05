# Date: 2 February, 2026
# Scope: Automated R-script to transform InstaScope sensor records into bioaerosol concentrations.
# Usage (already incorporated into Automate.py): ./bioserosol_script.r -i input_dir -o output_dir -f output_filename_prefix -t mins

# IMPORT LIBRARIES
suppressPackageStartupMessages({
  require("optparse", quietly = TRUE)
  require("data.table", quietly = TRUE)
  require("lubridate", quietly = TRUE)
  require("tidyverse", quietly = TRUE)
  require("magrittr", quietly = TRUE)
})

# PARSE ARGUMENTS
option_list = list(
  make_option(c("-i", "--input"), action="store", default=NA, type='character',
              help="File directory of InstaScope sensor records."),
  make_option(c("-o", "--output"), action="store", default=NA, type='character',
              help="Output directory of this program. Will be created if not existed."),
  make_option(c("-f", "--filename"), action="store", default="test", type='character',
              help="Filename prefix for output CSV file for bioaerosols concentration. [default: %default]"),
  make_option(c("-t", "--time"), action="store", default="secs",
              help="Time interval option for analysis. Options: {secs, mins, hours, days} [default: %default]"), 
  make_option(c("-v", "--verbose"), action="store_true", default=TRUE,
              help="(#Function to be developed) Should the program print extra stuff out? [default: %default]")
)
opt = parse_args(OptionParser(option_list=option_list, 
                              description="
************************************************************************************************
    Automated R-script to transform InstaScope sensor records into bioaerosols concentration
************************************************************************************************
                              "))
# VALIDATE PARSED ARGUMENTS
if (opt$v) {
  cat("Parsed Variables:\n")
  print(paste("Input dir", opt$input, sep = ": "))
  print(paste("Output dir", opt$output, sep = ": "))
  print(paste("Time interval", opt$t, sep = ": "))
}

# FUNCTIONS DEFINITION
# FUNCTION: calculating the threshold, performed by the approach of mean + 3 * standard deviation
thresh_FT <- function(df, colname){
  std_dev3 <- df[,colname] %>% sd(na.rm=TRUE) %>% "*"(3)
  baseline <- df[,colname] %>% mean(na.rm=TRUE) %>% + std_dev3
  return(baseline)
}
# FUNCTION: analyze the FT and get the threshold, the returned result is the average of all FT files
analyze_FT <- function(FT_files){
  FT <- NULL
  thresh <- vector("numeric", 3)
  # merge all available FT files, execute the standard deviation for the whole combined data
  for(i in seq_along(FT_files)){
    FT_temp <- read.csv(file = FT_files[i], sep = ",", skip = 38, header = TRUE)
    if(is.null(FT)){FT <- FT_temp} else {FT <- bind_rows(FT, FT_temp)}
  }
  thresh <- c(thresh_FT(FT, "FL1_280"), thresh_FT(FT, "FL2_280"), thresh_FT(FT, "FL2_370"))
  return(thresh)
}
# FUNCTION: discriminate the particles, depends on fluorescent channels and size
check_class <- function(df, threshold){ 
  nonfluor <- c(df[,"FL1_280"] < threshold[1] & df[,"FL2_280"] < threshold[2] & df[,"FL2_370"] < threshold[3])
  bacteria <- c(df[,"FL1_280"] > threshold[1] & df[,"Size"] < 1)
  fungi <- c(df[,"FL1_280"] > threshold[1] & df[,"Size"] > 2 & df[,"Size"] < 9 | 
               df[,"FL1_280"] > threshold[1] & df[,"FL2_280"] > threshold[2] & df[,"Size"] > 2 & df[,"Size"] < 9)
  pollen <- c(df[,"FL1_280"] > threshold[1] & df[,"FL2_280"] > threshold[2] & df[,"FL2_370"] > threshold[3] & df[,"Size"] > 2 & df[,"Size"] < 10 | 
                df[,"FL2_280"] > threshold[2] & df[,"FL2_370"] > threshold[3] & df[,"Size"] > 2 & df[,"Size"] < 10)
  classification <- ifelse(nonfluor, "Non-fluorescence", 
                           ifelse(bacteria, "Bacteria", 
                                  ifelse(fungi, "Fungi",
                                         ifelse(pollen, "Pollen", "Fluorescent-others"))))
  return(classification)
} 
# FUNCTION: scan and identify all particles in AQ file 
analyze_AQ <- function(AQ_file){
  full_df <- NULL
  as.data.table(full_df)
  # print the number of AQ files to track progress
  cat(paste("\n", AQ_file, sep = ""))
  # open data exclusively for flow rate and start time
  AQ_temp <- read.csv(file = AQ_file, sep = ",", nrows = 37) %>% .[c(1,37),]
  # import the data to be processed 
  AQ_df <- read.csv(file = AQ_file, sep = ",", skip = 38, header = TRUE, skipNul = TRUE) %>%
    select(Time, FL1_280, FL2_280, FL2_370, TPCT2, Size, AF) %>% 
    slice(1:n()-1)
  # unify the time format to 24-hour
  if(grepl(x=as.character(AQ_temp[2]), pattern = "M") == FALSE){
    start_time <- AQ_temp[2] %>% 
      substr(start = 18, stop = 40) %>% 
      as.POSIXct(tryFormats = "%m/%d/%Y %H:%M:%S", tz = "Asia/Hong_Kong")}else{
        start_time <- AQ_temp[2] %>% 
          substr(start = 18, stop = 40) %>% 
          as.POSIXct(tryFormats = "%m/%d/%Y %I:%M:%S %p", tz = "Asia/Hong_Kong")}
  # create the full data frame 
  AQ_df <- AQ_df %>% 
    mutate(# check the class of particles
      classification = check_class(AQ_df, threshold),
      # beware of the time shift of each data set
      time = start_time + dseconds(AQ_df$Time/1000),
      # record flow rate in L/s of each AQ file
      flowrate_secs = AQ_temp[1] %>% substr(start = 18, stop = 22) %>% as.numeric() %>% "/"(10^6)) %>%
    select(-Time, -FL1_280, -FL2_280, -FL2_370)
  # supplement time resolution and filter the particulate matter 
  full_df <- AQ_df %>%
    mutate(mins = trunc(time, units = "mins"), 
           flowrate_mins = flowrate_secs*60,
           hours = trunc(time, units = "hours"), 
           flowrate_hours = flowrate_mins*60,
           days = trunc(time, units = "days"), 
           flowrate_days = flowrate_hours*24,
           pm2.5 = case_when(between(Size, 0, 2.5) ~ TRUE),
           pm10 = case_when(between(Size, 0, 10) ~ TRUE))  %>% 
    relocate(time, flowrate_secs, .after = time)
  return(full_df)
}
# FUNCTION: calculating the number concentration
no_conc <- function(full_df){
  # get flow rate of using time interval 
  flowrate_bytime <- paste("flowrate_", time_intvl, sep="")
  avg_flowrate <- mean(full_df[[flowrate_bytime]])
  # evaluate the counted particle without missed particle 
  no_conc_df <- full_df %>% 
    group_by_at(time_intvl) %>%
    count(classification) %>% 
    mutate(percent = n /sum(n)) %>%
    select(all_of(time_intvl), classification, n) %>% 
    ungroup() %>% na.omit() ## omit NA should be exercised 
  # align the time difference with the time interval
  diff_time <- full_df %>%
    select(time, !!time_intvl) %>% 
    group_by_at(time_intvl) %>% 
    summarise(diff = difftime(max(time), min(time), units= time_intvl)) %>%
    ungroup()
  # number concentration of total particles, including number and percent
  no_conc_df['conc'] <- 0
  for (row in 1:nrow(no_conc_df)){
    timediff <- as.numeric(diff_time$diff[diff_time[[time_intvl]] == no_conc_df[[time_intvl]][row]])
    no_conc_df$conc[row] <- no_conc_df$n[row] / (timediff * avg_flowrate)
  }
  no_conc_pa <- no_conc_df %>% select(-n) 
  # number concentration of all species, including pollen, fungi, and bacteria
  no_conc_sp <- no_conc_pa %>% 
    filter(!classification %in% c("Fluorescent-others", "Non-fluorescence")) 
  # number concentration of all particles 
  no_conc_all <- no_conc_pa %>%
    pivot_wider(names_from = classification, values_from = conc) %>%  
    mutate(across(.cols = c("Bacteria", "Pollen", "Fungi", "Fluorescent-others", "Non-fluorescence"), ~ replace(., is.na(.), 0))) %>%
    mutate('All-fluorescence' = Bacteria + Fungi + Pollen + `Fluorescent-others`, 
           'All-particles' =`All-fluorescence` + `Non-fluorescence`) %>%
    pivot_longer(2:8, names_to = "classification", values_to = "conc") %>% 
    arrange_at(time_intvl)
  # return species concentration
  return(no_conc_sp)
}
# MAIN PROGRAM
if(!is.na(opt$i) & !is.na(opt$o)) {
  # 1. Get input files ready.
  work_dir <- getwd()
  time_intvl <- opt$time
  in_dir <- file.path(opt$input)
  out_dir <-  file.path(opt$output) %T>% dir.create(showWarnings = FALSE)
  FT_file <- list.files(path = in_dir, pattern = "FT", full.names = TRUE)  # Get forced trigger (FT) file
  AQ_file <- list.files(path = in_dir, pattern = "AQ", full.names = TRUE) %>% as.list()  # Get  acquisition (AQ) file
  # Smarter way to read AQ_files, only read last or last-two files.
  len = length(AQ_file)
  if (len >=8){
    print("Ready to process AQ in 5 seconds...")
    Sys.sleep(5)
    AQ_file <- AQ_file[(len-7):(len-1)]
  } else if (len >= 3) {
    print("Ready to process AQ in 5 seconds...")
    Sys.sleep(5)
    AQ_file <- AQ_file[(len-2):(len-1)]
  }
  
  # 2. Classify different particles
  threshold <- analyze_FT(FT_file)
  full_df <- lapply(AQ_file, analyze_AQ) %>% bind_rows()
      # Calculate concentrations
  species_conc <- no_conc(full_df) %>%
    mutate(date = format(mins, format="%Y-%m-%d"),
           time= format(as.POSIXct(mins), format = "%H:%M:%S")) %>% 
    select(-mins) %>%
    relocate(date,.before = classification) %>% 
    relocate(time,.after = date)
    # Drop the initial-min and final-min due to incomplete sampling.
  final_time = species_conc$time[nrow(species_conc)]
  final_date = species_conc$date[nrow(species_conc)]
  initi_time = species_conc$time[1]
  initi_date = species_conc$date[1]
  species_conc_sub <- species_conc[!(species_conc$time==final_time & species_conc$date==final_date),]
  species_conc_sub <- species_conc_sub[!(species_conc_sub$time==initi_time & species_conc_sub$date==initi_date),]
  Filename <- paste(opt$filename, ".csv", sep="")
  write.csv(species_conc_sub, file = file.path(out_dir, Filename), row.names = FALSE)
} else {
  cat("[InputError] you didn't specify both variables for input directory and output directory.\n", file=stderr()) # print error messages to stderr
}
